"""헤드리스(offscreen) 스모크 테스트.

GUI를 띄우지 않고(QT_QPA_PLATFORM=offscreen) 렌더링/오버레이/설정창이
예외 없이 생성·그리기 되는지 확인한다. 전역 후킹과 시스템 커서 숨김은
부작용이 있으므로 호출하지 않는다.
"""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_SCALE_FACTOR"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtGui import QPainter, QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from mousepointerfx import config as cfgmod  # noqa: E402
from mousepointerfx import cursor_renderer as render  # noqa: E402
from mousepointerfx import win_cursor  # noqa: E402
from mousepointerfx.effects import Ripple  # noqa: E402
from mousepointerfx.overlay import Overlay  # noqa: E402
from mousepointerfx.settings_window import SettingsWindow  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    cfg = cfgmod.default_config()

    # 1) 모든 포인터 스타일 + 클릭 스타일 + 트레일을 픽스맵에 그려본다
    pm = QPixmap(200, 200)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    for style in cfgmod.POINTER_STYLES:
        cfg["pointer"]["style"] = style
        render.draw_pointer(p, 100, 100, cfg["pointer"])
    for style in cfgmod.CLICK_STYLES:
        rp = Ripple(100, 100, "#3DA5FF", 60, 0.45, 4, start=0.0, style=style)
        render.draw_click(p, rp, now=0.2)
    render.draw_trail(p, [(10, 10, 1.0), (20, 20, 0.5), (30, 30, 0.1)], "#FF2D2D", 18, True)
    p.end()
    print("[ok] renderer: 모든 스타일 그리기 통과")

    # 2) win_cursor: 빈 커서 핸들 생성만 검증(시스템 커서는 건드리지 않음)
    h = win_cursor._make_blank_cursor()
    assert h, "빈 커서 핸들 생성 실패"
    print("[ok] win_cursor: 빈 커서 생성 통과")

    # 3) 설정창 구성(표시는 안 함)
    captured = {}
    sw = SettingsWindow(cfg, lambda c: captured.update(c=c))
    sw._reset()  # 초기화 → UI 재구성 경로 검증
    assert "c" in captured
    print("[ok] settings_window: 구성/초기화 통과")

    # 4) 오버레이 생성 + 클릭/레이저/틱 + 실제 페인트(grab)
    cfg2 = cfgmod.default_config()
    ov = Overlay(cfg2)
    ov.resize(300, 300)
    ov.on_click(50, 50, "left")
    ov.on_click(60, 60, "right")
    ov.set_laser(True)
    ov._tick()
    _ = ov.grab()       # paintEvent 강제 실행
    ov.set_laser(False)
    ov.apply_config(cfgmod.default_config())
    _ = ov.grab()
    print("[ok] overlay: 생성/클릭/레이저/페인트 통과")

    # 5) keycast: 토글 + 키 이벤트 피드 + 페인트
    ov.set_keycast(True)
    ov.feed_key({"kind": "char", "ch": "a"})
    ov.feed_key({"kind": "combo", "mods": ["ctrl", "alt"], "key": "C", "key_is_special": False})
    ov.feed_key({"kind": "special", "name": "enter"})
    ov.feed_key({"kind": "hangul_toggle"})
    for ch in ("g", "k", "s"):
        ov.feed_key({"kind": "char", "ch": ch})
    assert ov.keycast.text(), "keycast 표시 문자열이 비어있음"
    _ = ov.grab()
    ov.set_keycast(False)
    print("[ok] overlay: keycast 토글/피드/페인트 통과")

    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
