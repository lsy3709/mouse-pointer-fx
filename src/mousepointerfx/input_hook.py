"""전역 마우스 클릭 + 단축키 + (선택적) 키 입력 캡처 → Qt 시그널 브리지 (pynput).

단축키는 pynput GlobalHotKeys 대신 **VK 코드 기준 직접 매칭**으로 처리한다.
(GlobalHotKeys 는 Ctrl+Alt+문자 조합에서 'k'가 제어문자로 바뀌어 매칭에 실패하는
알려진 문제가 있다. vk 는 모디파이어/IME/레이아웃과 무관하게 일정하므로 안정적이다.)

하나의 상시 키보드 리스너가 (1) 단축키 매칭과 (2) keycast 표시 캡처를 함께 처리한다.
캡처(표시)는 keycast 가 켜졌을 때만 동작한다(프라이버시/성능). 단축키 매칭은 항상.

pynput 콜백은 별도 스레드에서 호출되므로 Qt 객체에 직접 접근하지 않고 시그널만 emit.
콜백은 무거운 작업(예: IME 조회) 없이 가볍게 유지한다(저수준 후킹 지연 방지).
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal
from pynput import keyboard, mouse

_MOD_MAP = {
    "ctrl_l": "ctrl", "ctrl_r": "ctrl",
    "alt_l": "alt", "alt_r": "alt", "alt_gr": "alt",
    "shift": "shift", "shift_r": "shift",
    "cmd": "win", "cmd_l": "win", "cmd_r": "win",
}
_VK_HANGUL = 0x15   # 한/영 키
_VK_HANJA = 0x19
_VK_F1 = 0x70


def _key_vk(key):
    """pynput 키에서 가상 키코드를 견고하게 추출(KeyCode.vk 또는 Key.value.vk)."""
    vk = getattr(key, "vk", None)
    if vk is None:
        vk = getattr(getattr(key, "value", None), "vk", None)
    return vk


def _token_vk(tok: str):
    """단축키 문자열의 마지막 키 토큰 → vk. (a-z, 0-9, f1-f24, 일부 특수)"""
    t = tok.strip().lower().strip("<>")
    if len(t) == 1:
        c = t.upper()
        if "A" <= c <= "Z" or "0" <= c <= "9":
            return ord(c)
    if t.startswith("f") and t[1:].isdigit():
        n = int(t[1:])
        if 1 <= n <= 24:
            return _VK_F1 + (n - 1)
    return {"space": 0x20, "enter": 0x0D, "tab": 0x09, "esc": 0x1B,
            "home": 0x24, "end": 0x23, "insert": 0x2D, "delete": 0x2E}.get(t)


def parse_hotkey(spec: str):
    """'<ctrl>+<alt>+k' → (frozenset({'ctrl','alt'}), 75). 파싱 실패 시 None."""
    if not spec:
        return None
    mods, vk = set(), None
    for tok in spec.split("+"):
        t = tok.strip().lower().strip("<>")
        if t in ("ctrl", "control"):
            mods.add("ctrl")
        elif t in ("alt", "alt_gr"):
            mods.add("alt")
        elif t == "shift":
            mods.add("shift")
        elif t in ("cmd", "win", "super"):
            mods.add("win")
        elif t:
            vk = _token_vk(t)
    if vk is None:
        return None
    return (frozenset(mods), vk)


def _combo_key_label(key, ch) -> str:
    """조합키(Ctrl/Alt/Win + X)에서 X 의 표시 라벨. char 가 제어문자/None 이어도 vk로 복원."""
    vk = _key_vk(key)
    if vk is not None:
        if 65 <= vk <= 90 or 48 <= vk <= 57:
            return chr(vk)
        if 96 <= vk <= 105:
            return str(vk - 96)
    if ch and ch.isprintable() and ord(ch) >= 32:
        return ch.upper()
    return f"VK{vk}" if vk else "?"


class InputBridge(QObject):
    clicked = pyqtSignal(int, int, str)       # x, y(물리 px), 'left'|'right'
    toggle_laser = pyqtSignal()
    toggle_keycast = pyqtSignal()
    key_event = pyqtSignal(object)            # dict (keycast 표시용)


class InputHook:
    """마우스 클릭 + 전역 단축키(레이저/keycast 토글) + 키 입력 캡처 관리."""

    def __init__(self, bridge: InputBridge, laser_hotkey: str,
                 keycast_hotkey: str = "<ctrl>+<alt>+k") -> None:
        self._bridge = bridge
        self._laser_combo = parse_hotkey(laser_hotkey)
        self._keycast_combo = parse_hotkey(keycast_hotkey)
        self._mouse: mouse.Listener | None = None
        self._listener: keyboard.Listener | None = None
        self._capture = False              # keycast 표시 캡처 on/off
        self._mods: set[str] = set()       # 현재 눌린 모디파이어
        self._down: set[int] = set()       # 현재 눌린 비모디파이어 vk(오토리피트 판별)

    # ------------------------------------------------------------ 마우스
    def _on_click(self, x, y, button, pressed):
        if not pressed:
            return
        if button == mouse.Button.left:
            self._bridge.clicked.emit(int(x), int(y), "left")
        elif button == mouse.Button.right:
            self._bridge.clicked.emit(int(x), int(y), "right")

    # ------------------------------------------------------------ 키보드(상시)
    @staticmethod
    def _mod_name(key):
        if isinstance(key, keyboard.Key):
            return _MOD_MAP.get(key.name)
        return None

    @staticmethod
    def _match(combo, mods, vk) -> bool:
        if combo is None or vk is None:
            return False
        want_mods, want_vk = combo
        return vk == want_vk and want_mods <= mods

    def _on_release(self, key):
        m = self._mod_name(key)
        if m:
            self._mods.discard(m)
            return
        self._down.discard(_key_vk(key))

    def _on_press(self, key):
        m = self._mod_name(key)
        if m:
            self._mods.add(m)
            return
        vk = _key_vk(key)
        mods = frozenset(self._mods)

        is_repeat = vk in self._down
        if vk is not None:
            self._down.add(vk)

        # 단축키 매칭(항상, vk 기준). 오토리피트는 1회만.
        matched = False
        if not is_repeat:
            if self._match(self._keycast_combo, mods, vk):
                self._bridge.toggle_keycast.emit()
                matched = True
            elif self._match(self._laser_combo, mods, vk):
                self._bridge.toggle_laser.emit()
                matched = True

        # keycast 표시 캡처(켜졌을 때만)
        if self._capture and not matched:
            self._emit_keycast(key, vk, mods)

    def _emit_keycast(self, key, vk, mods):
        if vk == _VK_HANGUL:
            self._bridge.key_event.emit({"kind": "hangul_toggle"})
            return
        if vk == _VK_HANJA:
            return
        combo = bool(mods & {"ctrl", "alt", "win"})
        if isinstance(key, keyboard.Key):
            name = key.name
            if not combo and name == "backspace":
                self._bridge.key_event.emit({"kind": "backspace"})
                return
            if not combo and name == "space":
                self._bridge.key_event.emit({"kind": "space"})
                return
            if combo:
                self._bridge.key_event.emit(
                    {"kind": "combo", "mods": sorted(mods), "key": name, "key_is_special": True})
            else:
                self._bridge.key_event.emit({"kind": "special", "name": name})
            return
        ch = getattr(key, "char", None)
        if combo:
            self._bridge.key_event.emit(
                {"kind": "combo", "mods": sorted(mods),
                 "key": _combo_key_label(key, ch), "key_is_special": False})
        elif ch is not None:
            self._bridge.key_event.emit({"kind": "char", "ch": ch})

    # ------------------------------------------------------------ 핫키 변경
    def set_hotkey(self, hotkey: str):           # 레이저(기존 호환)
        self._laser_combo = parse_hotkey(hotkey)

    def set_keycast_hotkey(self, hotkey: str):
        self._keycast_combo = parse_hotkey(hotkey)

    # ------------------------------------------------------------ 캡처 on/off
    def start_capture(self):
        self._capture = True

    def stop_capture(self):
        self._capture = False

    # ------------------------------------------------------------ 수명
    def start(self):
        self._mouse = mouse.Listener(on_click=self._on_click)
        self._mouse.daemon = True
        self._mouse.start()
        self._listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self._listener.daemon = True
        self._listener.start()

    def stop(self):
        for listener in (self._mouse, self._listener):
            if listener is not None:
                try:
                    listener.stop()
                except Exception:
                    pass
        self._mouse = None
        self._listener = None
