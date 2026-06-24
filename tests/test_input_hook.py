"""input_hook 키 분류 로직 단위 테스트(실제 리스너 없이 _on_press 직접 호출)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pynput import keyboard  # noqa: E402

from mousepointerfx.input_hook import InputHook  # noqa: E402


class _Sig:
    def __init__(self):
        self.calls = []

    def emit(self, *a):
        self.calls.append(a[0] if len(a) == 1 else a)


class _Bridge:
    def __init__(self):
        self.key_event = _Sig()
        self.toggle_laser = _Sig()
        self.toggle_keycast = _Sig()
        self.clicked = _Sig()


def make_hook():
    h = InputHook(_Bridge(), "<ctrl>+<alt>+l", "<ctrl>+<alt>+k")
    h._capture = True   # 표시 캡처 켠 상태로 분류 로직 검증
    return h


def last(hook):
    return hook._bridge.key_event.calls[-1]


def test_plain_char():
    h = make_hook()
    h._on_press(keyboard.KeyCode(char="a", vk=65))
    assert last(h) == {"kind": "char", "ch": "a"}


def test_space_and_backspace():
    h = make_hook()
    h._on_press(keyboard.Key.space)
    assert last(h) == {"kind": "space"}
    h._on_press(keyboard.Key.backspace)
    assert last(h) == {"kind": "backspace"}


def test_special_enter():
    h = make_hook()
    h._on_press(keyboard.Key.enter)
    assert last(h) == {"kind": "special", "name": "enter"}


def test_modifier_alone_not_emitted():
    h = make_hook()
    n = len(h._bridge.key_event.calls)
    h._on_press(keyboard.Key.ctrl_l)   # 모디파이어 단독 → emit 안 함
    assert len(h._bridge.key_event.calls) == n
    assert "ctrl" in h._mods


def test_ctrl_c_combo():
    h = make_hook()
    h._on_press(keyboard.Key.ctrl_l)
    h._on_press(keyboard.KeyCode(char="\x03", vk=67))  # Ctrl+C (char가 제어문자여도 vk로 복원)
    ev = last(h)
    assert ev["kind"] == "combo"
    assert "ctrl" in ev["mods"]
    assert ev["key"] == "C"
    assert ev["key_is_special"] is False


def test_combo_released_back_to_plain():
    h = make_hook()
    h._on_press(keyboard.Key.ctrl_l)
    h._on_release(keyboard.Key.ctrl_l)
    h._on_press(keyboard.KeyCode(char="d", vk=68))
    assert last(h) == {"kind": "char", "ch": "d"}


def test_hangul_toggle_key():
    h = make_hook()
    h._on_press(keyboard.KeyCode(vk=0x15))   # VK_HANGUL(한/영) — pynput 실제 표현
    assert last(h) == {"kind": "hangul_toggle"}


def test_hangul_toggle_key_value_vk_fallback():
    # 환경/버전에 따라 vk 가 .value.vk 에만 있는 경우도 잡혀야 함
    class _FakeKey:
        class value:
            vk = 0x15
    h = make_hook()
    h._on_press(_FakeKey())
    assert last(h) == {"kind": "hangul_toggle"}


def test_ctrl_alt_special_combo():
    h = make_hook()
    h._on_press(keyboard.Key.ctrl_l)
    h._on_press(keyboard.Key.alt_l)
    h._on_press(keyboard.Key.enter)
    ev = last(h)
    assert ev["kind"] == "combo"
    assert set(ev["mods"]) >= {"ctrl", "alt"}
    assert ev["key"] == "enter" and ev["key_is_special"] is True


# ---- 단축키 VK 매칭 (Ctrl+Alt+문자 인식 문제 수정) ----

def test_parse_hotkey():
    from mousepointerfx.input_hook import parse_hotkey
    assert parse_hotkey("<ctrl>+<alt>+k") == (frozenset({"ctrl", "alt"}), 75)
    assert parse_hotkey("<ctrl>+<shift>+p") == (frozenset({"ctrl", "shift"}), 80)
    assert parse_hotkey("<f8>") == (frozenset(), 0x77)
    assert parse_hotkey("") is None


def test_keycast_hotkey_fires_by_vk():
    h = make_hook()
    h._on_press(keyboard.Key.ctrl_l)
    h._on_press(keyboard.Key.alt_l)
    # Ctrl 눌림으로 char가 제어문자여도 vk=75 면 매칭돼야 함(기존 GlobalHotKeys 실패 케이스)
    h._on_press(keyboard.KeyCode(char="\x0b", vk=75))
    assert len(h._bridge.toggle_keycast.calls) == 1
    assert h._bridge.key_event.calls == []   # 핫키는 표시로 새지 않음


def test_laser_hotkey_fires_by_vk():
    h = make_hook()
    h._on_press(keyboard.Key.ctrl_l)
    h._on_press(keyboard.Key.alt_l)
    h._on_press(keyboard.KeyCode(char="\x0c", vk=76))   # L
    assert len(h._bridge.toggle_laser.calls) == 1


def test_hotkey_ignores_autorepeat():
    h = make_hook()
    h._on_press(keyboard.Key.ctrl_l)
    h._on_press(keyboard.Key.alt_l)
    for _ in range(3):                          # 누른 채 오토리피트
        h._on_press(keyboard.KeyCode(char="\x0b", vk=75))
    assert len(h._bridge.toggle_keycast.calls) == 1
    h._on_release(keyboard.KeyCode(vk=75))      # 뗐다가
    h._on_press(keyboard.KeyCode(char="\x0b", vk=75))   # 다시 누르면 재발동
    assert len(h._bridge.toggle_keycast.calls) == 2


def test_hotkey_needs_both_modifiers():
    h = make_hook()
    h._on_press(keyboard.Key.ctrl_l)            # alt 없이 ctrl+k
    h._on_press(keyboard.KeyCode(char="\x0b", vk=75))
    assert len(h._bridge.toggle_keycast.calls) == 0   # 발동 안 함


def test_no_capture_when_off():
    h = InputHook(_Bridge(), "<ctrl>+<alt>+l", "<ctrl>+<alt>+k")   # capture 기본 False
    h._on_press(keyboard.KeyCode(char="a", vk=65))
    assert h._bridge.key_event.calls == []
