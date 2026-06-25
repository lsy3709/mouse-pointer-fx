"""투명·항상위·클릭통과 풀스크린 오버레이.

가상 데스크톱 전체를 덮고, 그 위에 커스텀 포인터/클릭효과/레이저를 그린다.
입력은 통과시키므로 밑의 앱은 정상 동작한다.
"""
from __future__ import annotations

import time

import win32api
import win32con
import win32gui
from PyQt6.QtCore import QRect, Qt, QTimer
from PyQt6.QtGui import QGuiApplication, QPainter
from PyQt6.QtWidgets import QWidget

from . import cursor_renderer as render
from . import keycast as kc
from . import win_ime
from .effects import ClickEffects, LaserTrail, Ripple


class Overlay(QWidget):
    def __init__(self, cfg: dict) -> None:
        super().__init__()
        self.cfg = cfg
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self._origin = (0, 0)             # 가상 데스크톱 좌상단(물리 px)
        self._virt = None                 # 마지막 적용한 가상화면 (vx,vy,vw,vh)
        self._resync_div = 0              # 디스플레이 변경 감지 스로틀 카운터
        self._top_div = 0                 # topmost(z-순서) 재주장 스로틀 카운터
        self._cursor = (0, 0)             # 마지막 커서 위치(물리 px)
        self._prev_cursor = (0, 0)
        self._last_dirty = QRect()

        self.click_fx = ClickEffects()
        self.laser_trail = LaserTrail(lifetime=self._laser_lifetime())
        self.laser_active = False

        self.keycast = self._make_keycast()
        self.keycast_active = False
        self._kc_last_text = ""

        self._apply_geometry()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(self._interval_ms())
        self._top_target = max(1, round(70 / self._interval_ms()))  # ≈70ms 마다 재주장

        # 모니터 추가/제거/주화면 변경 시 즉시 재동기화
        # (화면 잠금/해제는 _tick 의 주기 감지가 보강한다)
        gapp = QGuiApplication.instance()
        if gapp is not None:
            gapp.screenAdded.connect(lambda *_: self._resync_display())
            gapp.screenRemoved.connect(lambda *_: self._resync_display())
            gapp.primaryScreenChanged.connect(lambda *_: self._resync_display())

    # ------------------------------------------------------------------ 설정값
    def _laser_lifetime(self) -> float:
        return max(0.05, self.cfg["laser"].get("trail_length_ms", 350) / 1000.0)

    def _interval_ms(self) -> int:
        hz = int(self.cfg["general"].get("update_hz", 120))
        hz = max(30, min(240, hz))
        return max(1, int(1000 / hz))

    # ------------------------------------------------------------------ 지오메트리
    def _read_virtual_metrics(self) -> tuple[int, int, int, int]:
        return (
            win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN),
            win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN),
            win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN),
            win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN),
        )

    def _apply_geometry(self) -> None:
        vx, vy, vw, vh = self._read_virtual_metrics()
        self._virt = (vx, vy, vw, vh)
        self._origin = (vx, vy)
        self.setGeometry(vx, vy, vw, vh)

    def _resync_display(self) -> None:
        """현재 가상 화면에 맞춰 지오메트리/클릭통과 스타일/z-순서를 재적용.

        화면 잠금/해제·해상도·모니터·DPI 변경 후 생기는 위치 어긋남을 자동 보정한다.
        (기존엔 설정/포인터 토글 시 apply_config 가 호출돼야만 맞춰졌다.)
        """
        self._apply_geometry()
        self._apply_exstyles()
        self.raise_()
        self._reassert_topmost()
        self.update()

    def _check_display_change(self) -> None:
        """가상화면 메트릭이 시작값과 달라졌으면 재동기화."""
        try:
            cur = self._read_virtual_metrics()
        except Exception:
            return
        if cur != self._virt:
            self._resync_display()

    def _reassert_topmost(self) -> None:
        """다른 창(특히 topmost 창)에 가려져 커서가 사라지지 않도록 z-순서를 위로 재주장.

        시스템 커서를 전역으로 숨긴 상태에서 오버레이가 뒤로 밀리면 그 위에선 커서가
        완전히 안 보이게 된다. 그릴 게 있을 때 주기적으로 HWND_TOPMOST 로 끌어올린다.
        """
        if not (self.cfg["pointer"].get("enabled", True)
                or self.laser_active or self.keycast_active):
            return
        try:
            hwnd = int(self.winId())
            win32gui.SetWindowPos(
                hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
                | win32con.SWP_NOACTIVATE | win32con.SWP_NOOWNERZORDER)
        except Exception:
            pass

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self._apply_exstyles()

    def _apply_exstyles(self) -> None:
        """Win32 확장 스타일로 클릭통과/툴윈도우/비활성 보장."""
        try:
            hwnd = int(self.winId())
            ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            ex |= (win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
                   | win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_NOACTIVATE)
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex)
        except Exception:
            pass

    # ------------------------------------------------------------------ 외부 API
    def apply_config(self, cfg: dict) -> None:
        prev_hangul = self.keycast.hangul if getattr(self, "keycast", None) else False
        self.cfg = cfg
        self.laser_trail.lifetime = self._laser_lifetime()
        self.keycast = self._make_keycast()
        if prev_hangul:
            self.keycast.set_hangul(True)
        self._kc_last_text = ""
        self._timer.start(self._interval_ms())
        self._top_target = max(1, round(70 / self._interval_ms()))
        self._apply_geometry()
        self.update()

    # ------------------------------------------------------------------ keycast
    def _make_keycast(self):
        k = self.cfg["keycast"]
        return kc.KeyCast(
            duration=max(0.2, k.get("duration_ms", 1500) / 1000.0),
            max_len=int(k.get("max_chars", 40)),
            hangul=bool(k.get("hangul", False)),
        )

    def _keycast_area(self) -> QRect:
        """keycast 를 그릴 영역 = 커서가 있는 모니터(위젯 로컬 좌표).

        다중 모니터에서 '화면 가운데'가 가상 데스크톱 전체 중앙(모니터 경계)이
        아니라 사용자가 보는 모니터 중앙이 되도록 한다.
        """
        try:
            flag = getattr(win32con, "MONITOR_DEFAULTTOPRIMARY", 1)
            hmon = win32api.MonitorFromPoint(tuple(self._cursor), flag)
            left, top, right, bottom = win32api.GetMonitorInfo(hmon)["Monitor"]
            ox, oy = self._origin
            return QRect(left - ox, top - oy, right - left, bottom - top)
        except Exception:
            return self.rect()

    def _keycast_band(self) -> QRect:
        area = self._keycast_area()
        k = self.cfg["keycast"]
        fs = float(k.get("font_size", 44))
        h = int(fs * 3)
        if k.get("position", "center") == "bottom":
            cy = int(area.bottom() - h / 2 - area.height() * 0.12)
        else:
            cy = area.center().y()
        return QRect(area.left(), max(area.top(), cy - h), area.width(), h * 2)

    def _refresh_keycast(self) -> None:
        """표시 문자열이 바뀌었으면(입력/만료) 중앙 띠만 부분 갱신."""
        cur = self.keycast.text() if self.keycast_active else ""
        if cur != self._kc_last_text:
            self._kc_last_text = cur
            self.update(self._keycast_band())

    def feed_key(self, ev) -> None:
        if not self.keycast_active or not isinstance(ev, dict):
            return
        kind = ev.get("kind")
        k = self.keycast
        if kind == "char":
            # OS 한/영(IME) 상태를 읽어 한글 조합 모드를 자동 동기화
            state = win_ime.foreground_hangul_state()
            if state is not None:
                k.set_hangul(state)
            k.feed_char(ev.get("ch", ""))
        elif kind == "space":
            k.feed_space()
        elif kind == "backspace":
            k.backspace()
        elif kind == "special":
            k.feed_special(ev.get("name", ""))
        elif kind == "combo":
            key = ev.get("key", "")
            if ev.get("key_is_special"):
                key = kc.special_name(key)
            k.feed_combo(kc.combo_label(ev.get("mods", []), key))
        elif kind == "hangul_toggle":
            k.toggle_hangul()
        self._refresh_keycast()

    def set_keycast(self, active: bool) -> None:
        self.keycast_active = active
        self._refresh_keycast()

    def on_click(self, gx: int, gy: int, button: str) -> None:
        c = self.cfg["click"]
        if not c.get("enabled", True):
            return
        ox, oy = self._origin
        color = c.get("left_color") if button == "left" else c.get("right_color")
        self.click_fx.add(Ripple(
            x=gx - ox, y=gy - oy, color=color or "#3DA5FF",
            max_radius=float(c.get("size", 60)),
            duration=max(0.05, c.get("duration_ms", 450) / 1000.0),
            thickness=float(c.get("thickness", 4)),
            start=time.monotonic(),
            style=c.get("style", "ripple"),
        ))

    def set_laser(self, active: bool) -> None:
        self.laser_active = active
        if not active:
            self.laser_trail.clear()
        self.update()

    # ------------------------------------------------------------------ 프레임 루프
    def _tick(self) -> None:
        # 디스플레이 변경(잠금/해제·해상도·모니터) 주기 감지 → 자동 원점 재동기화
        self._resync_div += 1
        if self._resync_div >= 30:
            self._resync_div = 0
            self._check_display_change()

        # 다른 창에 가려져 커서가 사라지지 않도록 z-순서(topmost)를 주기적으로 재주장
        self._top_div += 1
        if self._top_div >= self._top_target:
            self._top_div = 0
            self._reassert_topmost()

        # keycast 표시 만료/변경 시 중앙 띠 갱신(움직임 없어도 사라지게)
        self._refresh_keycast()

        now = time.monotonic()
        try:
            pos = win32api.GetCursorPos()
        except Exception:
            pos = self._cursor
        self._prev_cursor = self._cursor
        self._cursor = pos
        ox, oy = self._origin
        cx, cy = pos[0] - ox, pos[1] - oy

        moved = pos != self._prev_cursor

        if self.laser_active and self.cfg["laser"].get("trail", True):
            self.laser_trail.add(cx, cy, now)
        self.laser_trail.prune(now)
        self.click_fx.update(now)

        fx_active = self.click_fx.active(now) or (self.laser_active and len(self.laser_trail) > 0)
        pointer_visible = self.laser_active or self.cfg["pointer"].get("enabled", True)

        if not (moved or fx_active or (pointer_visible and moved)):
            if not fx_active and not moved:
                # 그릴 게 없고 움직임도 없으면 갱신 생략(CPU 절약)
                if self._last_dirty.isNull():
                    return
        # 더티 사각형 계산 후 부분 업데이트
        dirty = self._compute_dirty(now, cx, cy, pointer_visible)
        region = dirty.united(self._last_dirty)
        self._last_dirty = dirty
        if region.isNull():
            return
        self.update(region)

    def _compute_dirty(self, now: float, cx: float, cy: float, pointer_visible: bool) -> QRect:
        rect = QRect()

        def add(x, y, ext):
            nonlocal rect
            r = QRect(int(x - ext), int(y - ext), int(ext * 2), int(ext * 2))
            rect = r if rect.isNull() else rect.united(r)

        if pointer_visible:
            if self.laser_active:
                ext = float(self.cfg["laser"].get("dot_size", 18)) * 1.3 + 4
            else:
                ext = render.pointer_extent(self.cfg["pointer"])
            add(cx, cy, ext)

        for rp in self.click_fx.items():
            ext = rp.radius(now) + rp.thickness + 2
            add(rp.x, rp.y, ext)

        if self.laser_active:
            dot = float(self.cfg["laser"].get("dot_size", 18))
            for (x, y, _a) in self.laser_trail.points_with_alpha(now):
                add(x, y, dot)
        return rect

    # ------------------------------------------------------------------ 그리기
    def paintEvent(self, event):  # noqa: N802
        now = time.monotonic()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # 1) 레이저 트레일(맨 뒤)
        if self.laser_active and self.cfg["laser"].get("trail", True):
            pts = self.laser_trail.points_with_alpha(now)
            render.draw_trail(
                painter, pts,
                self.cfg["laser"].get("color", "#FF2D2D"),
                float(self.cfg["laser"].get("dot_size", 18)),
                glow=bool(self.cfg["laser"].get("glow", True)),
            )

        # 2) 클릭 효과
        for rp in self.click_fx.items():
            render.draw_click(painter, rp, now)

        # 3) 포인터 / 레이저 점(맨 위)
        ox, oy = self._origin
        cx, cy = self._cursor[0] - ox, self._cursor[1] - oy
        if self.laser_active:
            render.draw_laser_dot(
                painter, cx, cy,
                self.cfg["laser"].get("color", "#FF2D2D"),
                float(self.cfg["laser"].get("dot_size", 18)),
                glow=bool(self.cfg["laser"].get("glow", True)),
            )
        elif self.cfg["pointer"].get("enabled", True):
            render.draw_pointer(painter, cx, cy, self.cfg["pointer"])

        # 4) 키 입력 표시(keycast, 화면 중앙 굵은 흰 글씨)
        if self.keycast_active:
            text = self.keycast.text()
            if text:
                k = self.cfg["keycast"]
                render.draw_keycast(
                    painter, text, self._keycast_area(),
                    float(k.get("font_size", 44)),
                    color_hex=k.get("color", "#FFFFFF"),
                    bold=bool(k.get("bold", True)),
                    position=k.get("position", "center"),
                )

        painter.end()
