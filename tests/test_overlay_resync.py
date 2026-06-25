"""오버레이 디스플레이 재동기화 테스트.

화면 잠금/해제·해상도 변경 등으로 가상화면 메트릭(원점)이 바뀌면,
수동 토글(apply_config) 없이도 _tick 루프가 원점을 다시 읽어 맞춰야 한다.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import pytest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from mousepointerfx import config as cfgmod  # noqa: E402
from mousepointerfx import overlay as overlay_mod  # noqa: E402

import win32con  # noqa: E402

_app = QApplication.instance() or QApplication(sys.argv)


def _fake_metrics(origin_x, origin_y, w=1920, h=1080):
    table = {
        win32con.SM_XVIRTUALSCREEN: origin_x,
        win32con.SM_YVIRTUALSCREEN: origin_y,
        win32con.SM_CXVIRTUALSCREEN: w,
        win32con.SM_CYVIRTUALSCREEN: h,
    }
    return lambda metric: table[metric]


@pytest.fixture
def overlay(monkeypatch):
    # 시작 시 알려진 원점(0,0)에서 출발
    monkeypatch.setattr(overlay_mod.win32api, "GetSystemMetrics", _fake_metrics(0, 0))
    monkeypatch.setattr(overlay_mod.win32api, "GetCursorPos", lambda: (0, 0))
    ov = overlay_mod.Overlay(cfgmod.default_config())
    yield ov
    ov.close()


def test_origin_resyncs_after_virtual_screen_shift(overlay, monkeypatch):
    assert overlay._origin == (0, 0)

    # 잠금/해제로 보조 모니터 구성이 바뀐 상황: 가상화면 원점이 이동
    monkeypatch.setattr(overlay_mod.win32api, "GetSystemMetrics", _fake_metrics(-1920, 0))
    monkeypatch.setattr(overlay_mod.win32api, "GetCursorPos", lambda: (0, 0))

    # 사용자가 아무 설정도 만지지 않고 프레임 루프만 도는 상황
    for _ in range(40):
        overlay._tick()

    assert overlay._origin == (-1920, 0)  # 수동 토글 없이 자동 재동기화돼야 함


def test_cursor_mapping_uses_resynced_origin(overlay, monkeypatch):
    # 원점이 (100,50)으로 바뀌면, 전역 커서 (100,50)은 위젯 로컬 (0,0)에 매핑돼야 한다
    monkeypatch.setattr(overlay_mod.win32api, "GetSystemMetrics", _fake_metrics(100, 50))
    monkeypatch.setattr(overlay_mod.win32api, "GetCursorPos", lambda: (100, 50))
    for _ in range(40):
        overlay._tick()
    ox, oy = overlay._origin
    assert (ox, oy) == (100, 50)
    # on_click 도 갱신된 원점으로 매핑
    overlay.on_click(100, 50, "left")
    rp = overlay.click_fx.items()[-1]
    assert (round(rp.x), round(rp.y)) == (0, 0)


def test_keycast_area_uses_cursor_monitor_local(overlay, monkeypatch):
    # 커서가 있는 모니터(가상 물리 사각형) → 위젯 로컬 좌표로 변환되는지
    overlay._origin = (-1000, -200)
    monkeypatch.setattr(overlay_mod.win32api, "MonitorFromPoint", lambda *a, **k: 7)
    monkeypatch.setattr(overlay_mod.win32api, "GetMonitorInfo",
                        lambda h: {"Monitor": (-1000, -200, 920, 880)})
    overlay._cursor = (-500, 100)
    r = overlay._keycast_area()
    # 로컬 = 가상좌표 - 원점(-1000,-200) → (0,0, 1920x1080)
    assert (r.left(), r.top(), r.width(), r.height()) == (0, 0, 1920, 1080)


def test_keycast_area_falls_back_on_error(overlay, monkeypatch):
    def boom(*a, **k):
        raise OSError("no monitor")
    monkeypatch.setattr(overlay_mod.win32api, "MonitorFromPoint", boom)
    r = overlay._keycast_area()
    assert r == overlay.rect()   # 실패 시 전체 위젯으로 폴백


def test_keycast_syncs_hangul_when_ime_native(overlay, monkeypatch):
    # OS IME 가 한글(native) → 영문 키여도 한글로 조합돼야 함
    monkeypatch.setattr(overlay_mod.win_ime, "foreground_hangul_state", lambda: True)
    overlay.set_keycast(True)
    for ch in ("g", "k", "s"):     # 두벌식 ㅎㅏㄴ
        overlay.feed_key({"kind": "char", "ch": ch})
    assert overlay.keycast.text() == "한"


def test_keycast_shows_latin_when_ime_english(overlay, monkeypatch):
    monkeypatch.setattr(overlay_mod.win_ime, "foreground_hangul_state", lambda: False)
    overlay.set_keycast(True)
    for ch in ("g", "k", "s"):
        overlay.feed_key({"kind": "char", "ch": ch})
    assert overlay.keycast.text() == "gks"


def test_keycast_ime_unknown_keeps_default(overlay, monkeypatch):
    # 감지 실패(None) → 기존 모드(기본 영문) 유지
    monkeypatch.setattr(overlay_mod.win_ime, "foreground_hangul_state", lambda: None)
    overlay.set_keycast(True)
    overlay.feed_key({"kind": "char", "ch": "a"})
    assert overlay.keycast.text() == "a"


def test_reasserts_topmost_periodically(overlay, monkeypatch):
    # 포인터가 보이는 상태(시스템 커서 숨김 케이스)에서는 z-순서를 주기적으로 재주장해야 함
    calls = []
    monkeypatch.setattr(overlay_mod.win32gui, "SetWindowPos",
                        lambda hwnd, after, *a, **k: calls.append(after))
    overlay.cfg["pointer"]["enabled"] = True
    overlay.laser_active = False
    overlay.keycast_active = False
    for _ in range(60):
        overlay._tick()
    assert any(after == overlay_mod.win32con.HWND_TOPMOST for after in calls), \
        "_tick 이 HWND_TOPMOST 로 z-순서를 재주장하지 않음"


def test_no_topmost_reassert_when_idle(overlay, monkeypatch):
    # 아무것도 그리지 않고 시스템 커서도 안 숨기는 상태면 z-순서를 건드리지 않음
    calls = []
    monkeypatch.setattr(overlay_mod.win32gui, "SetWindowPos",
                        lambda *a, **k: calls.append(a))
    overlay.cfg["pointer"]["enabled"] = False
    overlay.laser_active = False
    overlay.keycast_active = False
    for _ in range(60):
        overlay._tick()
    assert calls == []


def test_no_resync_when_metrics_unchanged(overlay, monkeypatch):
    calls = {"n": 0}
    orig = overlay._resync_display

    def counting():
        calls["n"] += 1
        orig()

    monkeypatch.setattr(overlay, "_resync_display", counting)
    # 메트릭 그대로(0,0) → 여러 프레임 돌려도 재동기화 안 일어나야 함
    for _ in range(100):
        overlay._tick()
    assert calls["n"] == 0
