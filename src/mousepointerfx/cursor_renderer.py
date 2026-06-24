"""포인터/클릭/레이저의 실제 픽셀 그리기 (QPainter).

overlay 가 paintEvent 에서 호출한다. 좌표는 위젯 로컬(px).
"""
from __future__ import annotations

import math

from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QFontMetrics, QPainter, QPen, QPolygonF, QRadialGradient,
)

from .effects import Ripple


def _qcolor(hex_str: str, alpha: int = 255) -> QColor:
    c = QColor(hex_str)
    if not c.isValid():
        c = QColor("#FF2D2D")
    c.setAlpha(max(0, min(255, alpha)))
    return c


# ---------------------------------------------------------------- 포인터/레이저 점

def draw_laser_dot(painter: QPainter, x: float, y: float, color_hex: str,
                   diameter: float, glow: bool = True, opacity: int = 100) -> None:
    """파워포인트형 레이저 점: 밝은 중심 + 색 코어 + 번지는 글로우."""
    base = QColor(color_hex)
    if not base.isValid():
        base = QColor("#FF2D2D")
    op = max(0.0, min(1.0, opacity / 100.0))
    core_r = max(2.0, diameter / 2.0)
    halo_r = core_r * (2.3 if glow else 1.15)

    def a(v: float) -> int:
        return int(max(0, min(255, v * op)))

    # 중심을 흰빛에 가깝게(핫스팟)
    hot = QColor(
        int(base.red() * 0.25 + 255 * 0.75),
        int(base.green() * 0.25 + 255 * 0.75),
        int(base.blue() * 0.25 + 255 * 0.75),
    )
    grad = QRadialGradient(QPointF(x, y), halo_r)
    grad.setColorAt(0.0, QColor(hot.red(), hot.green(), hot.blue(), a(255)))
    grad.setColorAt(0.18, QColor(base.red(), base.green(), base.blue(), a(255)))
    grad.setColorAt(0.45, QColor(base.red(), base.green(), base.blue(), a(215)))
    grad.setColorAt(1.0, QColor(base.red(), base.green(), base.blue(), 0))

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(grad))
    painter.drawEllipse(QPointF(x, y), halo_r, halo_r)


def _arrow_polygon(x: float, y: float, size: float) -> QPolygonF:
    """팁이 (x, y)에 오는 고전 화살표 커서 모양."""
    s = size / 22.0  # 정규화 좌표를 size 기준으로 스케일
    pts = [
        (0, 0), (0, 16), (3.5, 12.5), (6.5, 19),
        (9, 18), (6, 11.5), (11, 11.5),
    ]
    return QPolygonF([QPointF(x + px * s, y + py * s) for px, py in pts])


def draw_pointer(painter: QPainter, x: float, y: float, cfg: dict) -> None:
    """cfg = config['pointer'] 에 따라 포인터를 그린다."""
    style = cfg.get("style", "laser")
    color = cfg.get("color", "#FF2D2D")
    size = float(cfg.get("size", 28))
    glow = bool(cfg.get("glow", True))
    outline = bool(cfg.get("outline", False))
    outline_color = cfg.get("outline_color", "#FFFFFF")
    opacity = int(cfg.get("opacity", 100))
    alpha = int(255 * max(0, min(100, opacity)) / 100)

    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    if style == "laser":
        draw_laser_dot(painter, x, y, color, size, glow, opacity)
        return

    pen = QPen(_qcolor(outline_color, alpha)) if outline else QPen(Qt.PenStyle.NoPen)
    pen.setWidthF(max(1.0, size * 0.08))
    r = size / 2.0

    if style == "dot":
        painter.setPen(pen if outline else Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(_qcolor(color, alpha)))
        painter.drawEllipse(QPointF(x, y), r, r)

    elif style == "ring":
        ringpen = QPen(_qcolor(color, alpha))
        ringpen.setWidthF(max(2.0, size * 0.14))
        painter.setPen(ringpen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(x, y), r, r)

    elif style == "circle":
        painter.setPen(pen if outline else Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(_qcolor(color, int(alpha * 0.45))))
        painter.drawEllipse(QPointF(x, y), r, r)

    elif style == "cross":
        cpen = QPen(_qcolor(color, alpha))
        cpen.setWidthF(max(2.0, size * 0.12))
        cpen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(cpen)
        gap = r * 0.25
        painter.drawLine(QLineF(x - r, y, x - gap, y))
        painter.drawLine(QLineF(x + gap, y, x + r, y))
        painter.drawLine(QLineF(x, y - r, x, y - gap))
        painter.drawLine(QLineF(x, y + gap, x, y + r))

    elif style == "arrow":
        poly = _arrow_polygon(x, y, size)
        apen = QPen(_qcolor(outline_color, alpha))
        apen.setWidthF(max(1.0, size * 0.06))
        apen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(apen if outline else Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(_qcolor(color, alpha)))
        painter.drawPolygon(poly)
    else:
        draw_laser_dot(painter, x, y, color, size, glow, opacity)


def pointer_extent(cfg: dict) -> float:
    """더티 사각형 계산용: 포인터가 차지하는 중심 기준 반경(px)."""
    size = float(cfg.get("size", 28))
    if cfg.get("style", "laser") == "laser":
        return size * 1.2 + 4
    return size * 1.2 + 4


# ---------------------------------------------------------------- 클릭 효과

def draw_click(painter: QPainter, ripple: Ripple, now: float) -> None:
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    a = ripple.alpha(now)
    if a <= 0:
        return
    r = ripple.radius(now)
    base_alpha = int(220 * a)
    col = _qcolor(ripple.color, base_alpha)
    style = ripple.style

    if style == "rings":
        for frac, mul in ((0.55, 0.5), (0.78, 0.75), (1.0, 1.0)):
            pen = QPen(_qcolor(ripple.color, int(base_alpha * mul)))
            pen.setWidthF(ripple.thickness)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(ripple.x, ripple.y), r * frac, r * frac)

    elif style == "burst":
        pen = QPen(col)
        pen.setWidthF(ripple.thickness)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        n = 8
        inner = r * 0.45
        for i in range(n):
            ang = (2 * math.pi / n) * i
            dx, dy = math.cos(ang), math.sin(ang)
            painter.drawLine(
                QLineF(ripple.x + dx * inner, ripple.y + dy * inner,
                       ripple.x + dx * r, ripple.y + dy * r))

    elif style == "highlight":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(_qcolor(ripple.color, int(110 * a))))
        rr = ripple.max_radius * 0.5
        painter.drawEllipse(QPointF(ripple.x, ripple.y), rr, rr)

    else:  # ripple (확산 링)
        pen = QPen(col)
        pen.setWidthF(ripple.thickness)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(ripple.x, ripple.y), r, r)


# ---------------------------------------------------------------- 레이저 트레일

def draw_trail(painter: QPainter, points, color_hex: str, dot_size: float,
               glow: bool = True) -> None:
    """points = [(x, y, alpha), ...] 오래된→최신."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    base = QColor(color_hex)
    if not base.isValid():
        base = QColor("#FF2D2D")
    for (x, y, a) in points:
        if a <= 0:
            continue
        rad = max(1.0, (dot_size / 2.0) * (0.35 + 0.65 * a))  # 옛 점일수록 작아짐
        if glow:
            grad = QRadialGradient(QPointF(x, y), rad * 1.6)
            grad.setColorAt(0.0, QColor(base.red(), base.green(), base.blue(), int(200 * a)))
            grad.setColorAt(1.0, QColor(base.red(), base.green(), base.blue(), 0))
            painter.setBrush(QBrush(grad))
            painter.drawEllipse(QPointF(x, y), rad * 1.6, rad * 1.6)
        else:
            painter.setBrush(QBrush(QColor(base.red(), base.green(), base.blue(), int(200 * a))))
            painter.drawEllipse(QPointF(x, y), rad, rad)


# ---------------------------------------------------------------- 키 입력 표시(keycast)

def draw_keycast(painter: QPainter, text: str, area, font_size: float,
                 color_hex: str = "#FFFFFF", bold: bool = True,
                 position: str = "center") -> None:
    """화면 중앙(또는 하단)에 굵은 흰 글씨로 키 입력을 표시.

    가독성을 위해 반투명 둥근 배경 + 그림자를 깐다. area = 그릴 영역(QRect).
    """
    if not text:
        return
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    font = QFont()
    font.setPointSizeF(max(8.0, float(font_size)))
    font.setBold(bool(bold))
    painter.setFont(font)
    fm = QFontMetrics(font)

    tw = fm.horizontalAdvance(text)
    th = fm.height()
    pad_x = font_size * 0.55
    pad_y = font_size * 0.30
    box_w = tw + pad_x * 2
    box_h = th + pad_y * 2

    cx = area.center().x()
    if position == "bottom":
        cy = area.bottom() - box_h / 2 - area.height() * 0.12
    else:
        cy = area.center().y()
    bx = cx - box_w / 2
    by = cy - box_h / 2

    # 반투명 둥근 배경
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(0, 0, 0, 150)))
    painter.drawRoundedRect(QRectF(bx, by, box_w, box_h), box_h * 0.25, box_h * 0.25)

    tx = bx + pad_x
    ty = by + pad_y + fm.ascent()
    # 그림자(가독성)
    painter.setPen(QColor(0, 0, 0, 210))
    painter.drawText(int(tx + 2), int(ty + 2), text)
    # 본문
    painter.setPen(_qcolor(color_hex, 255))
    painter.drawText(int(tx), int(ty), text)
