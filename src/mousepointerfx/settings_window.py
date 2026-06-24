"""설정 창 (탭: 포인터 / 클릭 / 레이저 / 일반).

컨트롤 변경 시 cfg(앱과 공유하는 dict)를 그 자리에서 갱신하고 on_change(cfg) 호출.
app 이 이를 받아 오버레이 적용 + 저장 + 커서 표시 갱신을 수행한다.
"""
from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSlider, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from . import config as cfgmod


class ColorButton(QPushButton):
    """현재 색을 보여주고 클릭하면 색 선택 다이얼로그를 여는 버튼."""

    def __init__(self, color_hex: str, on_pick: Callable[[str], None]) -> None:
        super().__init__()
        self._on_pick = on_pick
        self.setFixedSize(48, 24)
        self.set_color(color_hex)
        self.clicked.connect(self._pick)

    def set_color(self, color_hex: str) -> None:
        self._color = color_hex
        self.setStyleSheet(
            f"background-color: {color_hex}; border: 1px solid #888; border-radius: 4px;")

    def _pick(self) -> None:
        col = QColorDialog.getColor(QColor(self._color), self, "색 선택")
        if col.isValid():
            hexs = col.name(QColor.NameFormat.HexRgb).upper()
            self.set_color(hexs)
            self._on_pick(hexs)


class SettingsWindow(QWidget):
    def __init__(self, cfg: dict, on_change: Callable[[dict], None]) -> None:
        super().__init__()
        self.cfg = cfg
        self._on_change = on_change
        self.setWindowTitle("Mouse Pointer FX — 설정")
        self.setMinimumSize(440, 380)
        self.setStyleSheet("QWidget { font-size: 13px; }")

        self._status: QLabel | None = None
        self._root = QVBoxLayout(self)
        self._build_ui()

    def _clear_layout(self, layout) -> None:
        """레이아웃 내 위젯/하위 레이아웃을 모두 제거(재구성용)."""
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            else:
                sub = item.layout()
                if sub is not None:
                    self._clear_layout(sub)

    def _build_ui(self) -> None:
        # 기존 내용 제거 후 현재 cfg 기준으로 재구성(초기화 시 값 반영)
        self._clear_layout(self._root)

        tabs = QTabWidget()
        tabs.addTab(self._pointer_tab(), "포인터")
        tabs.addTab(self._click_tab(), "클릭")
        tabs.addTab(self._laser_tab(), "레이저")
        tabs.addTab(self._keycast_tab(), "키 입력")
        tabs.addTab(self._general_tab(), "일반")
        self._root.addWidget(tabs)

        note = QLabel("변경은 즉시 반영됩니다. ‘적용’은 저장을 확정합니다.")
        note.setStyleSheet("color:#888;")
        self._root.addWidget(note)

        # 하단 버튼 바: [기본값으로 초기화] ......... 상태  [적용] [닫기]
        bar = QHBoxLayout()
        reset = QPushButton("기본값으로 초기화")
        reset.clicked.connect(self._reset)
        bar.addWidget(reset)
        bar.addStretch(1)

        self._status = QLabel("")
        self._status.setStyleSheet("color:#2e9e44; font-weight:bold;")
        bar.addWidget(self._status)

        apply_btn = QPushButton("적용")
        apply_btn.setDefault(True)
        apply_btn.setMinimumWidth(72)
        apply_btn.clicked.connect(self._apply_clicked)
        bar.addWidget(apply_btn)

        close_btn = QPushButton("닫기")
        close_btn.setMinimumWidth(72)
        close_btn.clicked.connect(self.close)
        bar.addWidget(close_btn)

        self._root.addLayout(bar)

    def _apply_clicked(self) -> None:
        self._emit()
        self._flash_status("적용됨 ✓")

    def _flash_status(self, text: str) -> None:
        if self._status is not None:
            self._status.setText(text)
            QTimer.singleShot(1500, lambda: self._status and self._status.setText(""))

    # ------------------------------------------------------------ 공용 헬퍼
    def _emit(self) -> None:
        self._on_change(self.cfg)

    def _slider_row(self, lo, hi, value, setter) -> QHBoxLayout:
        row = QHBoxLayout()
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(lo, hi)
        s.setValue(int(value))
        sp = QSpinBox()
        sp.setRange(lo, hi)
        sp.setValue(int(value))
        s.valueChanged.connect(sp.setValue)
        sp.valueChanged.connect(s.setValue)

        def changed(v):
            setter(int(v))
            self._emit()

        sp.valueChanged.connect(changed)
        row.addWidget(s)
        row.addWidget(sp)
        return row

    def _combo(self, items, current, setter) -> QComboBox:
        c = QComboBox()
        c.addItems(items)
        if current in items:
            c.setCurrentText(current)

        def changed(text):
            setter(text)
            self._emit()

        c.currentTextChanged.connect(changed)
        return c

    def _check(self, text, value, setter) -> QCheckBox:
        cb = QCheckBox(text)
        cb.setChecked(bool(value))

        def changed(state):
            setter(bool(state))
            self._emit()

        cb.toggled.connect(changed)
        return cb

    # ------------------------------------------------------------ 탭들
    def _pointer_tab(self) -> QWidget:
        p = self.cfg["pointer"]
        w = QWidget()
        form = QFormLayout(w)

        g = self.cfg["general"]
        form.addRow(self._check("커스텀 포인터 사용 (효과/레이저 그리기)",
                                p["enabled"], lambda v: p.__setitem__("enabled", v)))
        form.addRow(self._check("🖱 시스템 커서와 함께 표시 (커서를 숨기지 않음)",
                                not g["hide_system_cursor"],
                                lambda v: g.__setitem__("hide_system_cursor", not v)))
        together_hint = QLabel("· 체크 → 실제 화살표 커서 위에 레이저 점이 같이 보임\n"
                               "· 해제 → 시스템 커서를 숨기고 커스텀 포인터로 대체")
        together_hint.setStyleSheet("color:#888;")
        form.addRow(together_hint)
        form.addRow("모양", self._combo(cfgmod.POINTER_STYLES, p["style"],
                                       lambda v: p.__setitem__("style", v)))
        cbtn = ColorButton(p["color"], lambda v: (p.__setitem__("color", v), self._emit()))
        form.addRow("색", cbtn)
        form.addRow("크기", self._slider_row(4, 120, p["size"],
                                            lambda v: p.__setitem__("size", v)))
        form.addRow("불투명도(%)", self._slider_row(10, 100, p["opacity"],
                                                  lambda v: p.__setitem__("opacity", v)))
        form.addRow(self._check("글로우(외곽 번짐)", p["glow"],
                                lambda v: p.__setitem__("glow", v)))
        ocbtn = ColorButton(p["outline_color"],
                            lambda v: (p.__setitem__("outline_color", v), self._emit()))
        form.addRow(self._check("외곽선", p["outline"], lambda v: p.__setitem__("outline", v)))
        form.addRow("외곽선 색", ocbtn)
        hint = QLabel("· laser = 파워포인트형 레이저 점(기본)")
        hint.setStyleSheet("color:#888;")
        form.addRow(hint)
        return w

    def _click_tab(self) -> QWidget:
        c = self.cfg["click"]
        w = QWidget()
        form = QFormLayout(w)
        form.addRow(self._check("클릭 애니메이션 사용", c["enabled"],
                                lambda v: c.__setitem__("enabled", v)))
        form.addRow("스타일", self._combo(cfgmod.CLICK_STYLES, c["style"],
                                         lambda v: c.__setitem__("style", v)))
        lb = ColorButton(c["left_color"], lambda v: (c.__setitem__("left_color", v), self._emit()))
        rb = ColorButton(c["right_color"], lambda v: (c.__setitem__("right_color", v), self._emit()))
        form.addRow("좌클릭 색", lb)
        form.addRow("우클릭 색", rb)
        form.addRow("크기", self._slider_row(20, 240, c["size"],
                                            lambda v: c.__setitem__("size", v)))
        form.addRow("지속시간(ms)", self._slider_row(100, 2000, c["duration_ms"],
                                                  lambda v: c.__setitem__("duration_ms", v)))
        form.addRow("선 두께", self._slider_row(1, 14, c["thickness"],
                                              lambda v: c.__setitem__("thickness", v)))
        return w

    def _laser_tab(self) -> QWidget:
        la = self.cfg["laser"]
        w = QWidget()
        form = QFormLayout(w)
        hk = QLineEdit(la["hotkey"])
        hk.setPlaceholderText("<ctrl>+<alt>+l")

        def hk_changed():
            la["hotkey"] = hk.text().strip() or "<ctrl>+<alt>+l"
            self._emit()

        hk.editingFinished.connect(hk_changed)
        form.addRow("단축키", hk)
        hkhint = QLabel("형식 예: <ctrl>+<alt>+l , <ctrl>+<shift>+p , <f8>")
        hkhint.setStyleSheet("color:#888;")
        form.addRow(hkhint)
        cb = ColorButton(la["color"], lambda v: (la.__setitem__("color", v), self._emit()))
        form.addRow("색", cb)
        form.addRow("점 크기", self._slider_row(6, 60, la["dot_size"],
                                              lambda v: la.__setitem__("dot_size", v)))
        form.addRow(self._check("트레일(잔상)", la["trail"],
                                lambda v: la.__setitem__("trail", v)))
        form.addRow("트레일 길이(ms)", self._slider_row(100, 1500, la["trail_length_ms"],
                                                     lambda v: la.__setitem__("trail_length_ms", v)))
        form.addRow(self._check("글로우", la["glow"], lambda v: la.__setitem__("glow", v)))
        form.addRow(self._check("시작 시 레이저 포인터 자동 켜기", la.get("start_active", False),
                                lambda v: la.__setitem__("start_active", v)))
        return w

    def _keycast_tab(self) -> QWidget:
        kc = self.cfg["keycast"]
        w = QWidget()
        form = QFormLayout(w)
        hk = QLineEdit(kc["hotkey"])
        hk.setPlaceholderText("<ctrl>+<alt>+k")

        def hk_changed():
            kc["hotkey"] = hk.text().strip() or "<ctrl>+<alt>+k"
            self._emit()

        hk.editingFinished.connect(hk_changed)
        form.addRow("토글 단축키", hk)
        cb = ColorButton(kc["color"], lambda v: (kc.__setitem__("color", v), self._emit()))
        form.addRow("글자 색", cb)
        form.addRow("글꼴 크기", self._slider_row(16, 120, kc["font_size"],
                                                lambda v: kc.__setitem__("font_size", v)))
        form.addRow("표시 시간(ms)", self._slider_row(300, 5000, kc["duration_ms"],
                                                   lambda v: kc.__setitem__("duration_ms", v)))
        form.addRow("최대 글자 수", self._slider_row(10, 120, kc["max_chars"],
                                                 lambda v: kc.__setitem__("max_chars", v)))
        form.addRow("위치", self._combo(["center", "bottom"], kc.get("position", "center"),
                                       lambda v: kc.__setitem__("position", v)))
        form.addRow(self._check("굵게", kc["bold"], lambda v: kc.__setitem__("bold", v)))
        form.addRow(self._check("한글 조합 모드(시작값)", kc["hangul"],
                                lambda v: kc.__setitem__("hangul", v)))
        form.addRow(self._check("시작 시 자동 켜기", kc.get("start_active", False),
                                lambda v: kc.__setitem__("start_active", v)))
        hint = QLabel("· 한글은 OS 한/영 상태에 자동 동기화 (감지 안 되는 앱은 한/영 키 또는 위 '한글 조합 모드')\n"
                      "· 영문·한글·숫자·기호·특수키·Ctrl/Alt/Win 조합 표시")
        hint.setStyleSheet("color:#888;")
        form.addRow(hint)
        return w

    def _general_tab(self) -> QWidget:
        g = self.cfg["general"]
        w = QWidget()
        form = QFormLayout(w)
        hint = QLabel("‘시스템 커서와 함께 표시’ 옵션은 [포인터] 탭에 있습니다.")
        hint.setStyleSheet("color:#888;")
        form.addRow(hint)
        form.addRow(self._check("Windows 시작 시 자동 실행", g["start_with_windows"],
                                lambda v: g.__setitem__("start_with_windows", v)))
        form.addRow("갱신 주기(Hz)", self._combo(["60", "120", "144"], str(g["update_hz"]),
                                              lambda v: g.__setitem__("update_hz", int(v))))
        return w

    # ------------------------------------------------------------ 초기화
    def _reset(self) -> None:
        defaults = cfgmod.default_config()
        for k in list(self.cfg.keys()):
            self.cfg[k] = defaults[k]
        self._emit()
        self._build_ui()  # 컨트롤 값 갱신을 위해 UI 재구성
