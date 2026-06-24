"""키캐스트(화면 키 입력 표시) 순수 로직 모듈.

PyQt/pynput/win32 등 무거운 의존성을 일절 import 하지 않는 순수 파이썬 표준
라이브러리 전용 모듈이라 헤드리스 단위 테스트가 가능하다.

구성:
  - QWERTY_TO_JAMO: 두벌식(2-set) QWERTY → 한글 자모 매핑
  - HangulAutomaton: 자모를 음절 블록으로 조합하는 오토마타
  - KeyCast: 최근 입력을 누적해 만료(auto-expire)되는 표시 버퍼
  - combo_label / special_name: 조합키·특수키 표시 토큰 변환 헬퍼
"""
from __future__ import annotations

import time
from typing import Callable, List, Optional

# ---------------------------------------------------------------------------
# 두벌식 매핑: QWERTY 라틴 문자 -> 한글 자모 (대문자 = shift 자모)
# ---------------------------------------------------------------------------
QWERTY_TO_JAMO: dict[str, str] = {
    # 자음(초성/종성)
    "r": "ㄱ", "R": "ㄲ", "s": "ㄴ", "e": "ㄷ", "E": "ㄸ",
    "f": "ㄹ", "a": "ㅁ", "q": "ㅂ", "Q": "ㅃ", "t": "ㅅ",
    "T": "ㅆ", "d": "ㅇ", "w": "ㅈ", "W": "ㅉ", "c": "ㅊ",
    "z": "ㅋ", "x": "ㅌ", "v": "ㅍ", "g": "ㅎ",
    # 모음(중성)
    "k": "ㅏ", "o": "ㅐ", "i": "ㅑ", "O": "ㅒ", "j": "ㅓ",
    "p": "ㅔ", "u": "ㅕ", "P": "ㅖ", "h": "ㅗ", "y": "ㅛ",
    "n": "ㅜ", "b": "ㅠ", "m": "ㅡ", "l": "ㅣ",
}

# ---------------------------------------------------------------------------
# 유니코드 한글 조합 테이블
# ---------------------------------------------------------------------------
_HANGUL_BASE = 0xAC00

# 초성 19개
_CHO = [
    "ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ",
    "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ",
]

# 중성 21개
_JUNG = [
    "ㅏ", "ㅐ", "ㅑ", "ㅒ", "ㅓ", "ㅔ", "ㅕ", "ㅖ", "ㅗ", "ㅘ",
    "ㅙ", "ㅚ", "ㅛ", "ㅜ", "ㅝ", "ㅞ", "ㅟ", "ㅠ", "ㅡ", "ㅢ", "ㅣ",
]

# 종성 28개(첫 항목은 받침 없음)
_JONG = [
    "", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ",
    "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ", "ㅅ",
    "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ",
]

# 빠른 역조회 인덱스
_CHO_IDX = {j: i for i, j in enumerate(_CHO)}
_JUNG_IDX = {j: i for i, j in enumerate(_JUNG)}
_JONG_IDX = {j: i for i, j in enumerate(_JONG) if j}

# 겹모음 결합: (기준모음, 추가모음) -> 결합모음
_VOWEL_COMBINE = {
    ("ㅗ", "ㅏ"): "ㅘ",
    ("ㅗ", "ㅐ"): "ㅙ",
    ("ㅗ", "ㅣ"): "ㅚ",
    ("ㅜ", "ㅓ"): "ㅝ",
    ("ㅜ", "ㅔ"): "ㅞ",
    ("ㅜ", "ㅣ"): "ㅟ",
    ("ㅡ", "ㅣ"): "ㅢ",
}
# 겹모음 분해(backspace 용): 결합모음 -> (기준모음, 추가모음)
_VOWEL_SPLIT = {v: k for k, v in _VOWEL_COMBINE.items()}

# 겹받침 결합: (기준종성, 추가자음) -> 결합종성
_JONG_COMBINE = {
    ("ㄱ", "ㅅ"): "ㄳ",
    ("ㄴ", "ㅈ"): "ㄵ",
    ("ㄴ", "ㅎ"): "ㄶ",
    ("ㄹ", "ㄱ"): "ㄺ",
    ("ㄹ", "ㅁ"): "ㄻ",
    ("ㄹ", "ㅂ"): "ㄼ",
    ("ㄹ", "ㅅ"): "ㄽ",
    ("ㄹ", "ㅌ"): "ㄾ",
    ("ㄹ", "ㅍ"): "ㄿ",
    ("ㄹ", "ㅎ"): "ㅀ",
    ("ㅂ", "ㅅ"): "ㅄ",
}
# 겹받침 분해(받침 이동/backspace 용): 결합종성 -> (앞자음, 뒷자음)
_JONG_SPLIT = {v: k for k, v in _JONG_COMBINE.items()}


def _is_consonant(jamo: str) -> bool:
    return jamo in _CHO_IDX


def _is_vowel(jamo: str) -> bool:
    return jamo in _JUNG_IDX


class HangulAutomaton:
    """두벌식 자모를 한글 음절 블록으로 조합하는 오토마타.

    내부 상태:
      - _committed: 이미 확정된(더 이상 조합에 영향 없는) 글자들의 문자열
      - _cho/_jung/_jong: 현재 조합중인 블록의 초/중/종성 자모(없으면 None/'')

    `text`는 (_committed + 현재 조합중 블록)을 합쳐 보여준다.
    """

    def __init__(self) -> None:
        self.reset()

    # ------------------------------------------------------------------
    # 상태 조회
    # ------------------------------------------------------------------
    def reset(self) -> None:
        self._committed: str = ""
        self._cho: Optional[str] = None
        self._jung: Optional[str] = None
        self._jong: str = ""
        # backspace 를 위한 입력 히스토리(자모 단위 되돌림용)
        self._history: List[str] = []

    def _current_block(self) -> str:
        """현재 조합중인 자모만으로 만들어지는 표시 문자열."""
        if self._cho is not None and self._jung is not None:
            cho = _CHO_IDX[self._cho]
            jung = _JUNG_IDX[self._jung]
            jong = _JONG_IDX.get(self._jong, 0) if self._jong else 0
            code = _HANGUL_BASE + (cho * 21 + jung) * 28 + jong
            return chr(code)
        if self._cho is not None:
            return self._cho
        if self._jung is not None:
            return self._jung
        return ""

    @property
    def text(self) -> str:
        """현재까지 조합된 전체 문자열(확정분 + 조합중 블록)."""
        return self._committed + self._current_block()

    @property
    def composing(self) -> bool:
        """현재 조합중(블록에 자모가 하나라도 있음)이면 True."""
        return self._cho is not None or self._jung is not None

    # ------------------------------------------------------------------
    # 입력
    # ------------------------------------------------------------------
    def feed(self, jamo: str) -> None:
        """자모 한 개를 입력해 조합을 진행한다."""
        if not jamo:
            return
        if _is_consonant(jamo):
            self._feed_consonant(jamo)
        elif _is_vowel(jamo):
            self._feed_vowel(jamo)
        else:
            # 자모가 아닌 문자는 조합을 확정하고 그대로 덧붙인다.
            self._commit_block()
            self._committed += jamo
            self._history.append("\x00")  # 비자모 표식
            return
        self._history.append(jamo)

    def _feed_consonant(self, c: str) -> None:
        # 빈 상태 -> 초성으로 시작
        if self._cho is None and self._jung is None:
            self._cho = c
            return
        # 초성만 있는 상태에서 또 자음 -> 앞 초성 확정, 새 초성 시작
        if self._cho is not None and self._jung is None:
            self._committed += self._cho
            self._cho = c
            self._jong = ""
            return
        # 중성까지 있는 상태 -> 종성으로 붙이거나 겹받침 시도
        if self._jung is not None:
            if not self._jong:
                if c in _JONG_IDX:
                    self._jong = c
                else:
                    # 종성이 될 수 없는 자음(ㄸㅃㅉ) -> 블록 확정 후 새 초성
                    self._commit_block()
                    self._cho = c
                return
            # 이미 종성이 있음 -> 겹받침 결합 시도
            combo = _JONG_COMBINE.get((self._jong, c))
            if combo is not None:
                self._jong = combo
                return
            # 결합 불가 -> 현재 블록 확정 후 새 초성 시작
            self._commit_block()
            self._cho = c
            return

    def _feed_vowel(self, v: str) -> None:
        # 빈 상태 -> 모음 단독(중성만) 표시
        if self._cho is None and self._jung is None:
            self._jung = v
            return
        # 초성만 있는 상태 -> 중성 결합
        if self._cho is not None and self._jung is None:
            self._jung = v
            return
        # 중성이 있고 종성이 없는 상태 -> 겹모음 결합 시도
        if self._jung is not None and not self._jong:
            combo = _VOWEL_COMBINE.get((self._jung, v))
            if combo is not None:
                self._jung = combo
                return
            # 결합 불가 -> 현재 블록 확정 후 새 블록(모음만)
            self._commit_block()
            self._jung = v
            return
        # 종성이 있는 상태에서 모음 입력 -> 받침 이동
        if self._jung is not None and self._jong:
            self._move_final_to_new_block(v)
            return

    def _move_final_to_new_block(self, v: str) -> None:
        """받침 이동: 종성을 떼어 새 음절의 초성으로 옮기고 모음을 붙인다.

        겹받침이면 앞 자음은 종성으로 남기고 뒤 자음만 이동한다.
        """
        jong = self._jong
        split = _JONG_SPLIT.get(jong)
        if split is not None:
            # 겹받침: 앞자음은 남기고 뒷자음 이동
            keep, move = split
            self._jong = keep
            self._commit_block()
            self._cho = move
            self._jung = v
            self._jong = ""
        else:
            # 단일 받침: 통째로 이동
            self._jong = ""
            self._commit_block()
            self._cho = jong
            self._jung = v
            self._jong = ""

    def _commit_block(self) -> None:
        """현재 조합중 블록을 _committed 에 확정하고 블록을 비운다."""
        self._committed += self._current_block()
        self._cho = None
        self._jung = None
        self._jong = ""

    # ------------------------------------------------------------------
    # 되돌림 / 확정
    # ------------------------------------------------------------------
    def backspace(self) -> bool:
        """한 단계(자모 단위)를 되돌린다. 되돌릴 게 있으면 True."""
        # 1) 현재 조합중 블록이 있으면 자모 단위로 분해
        if self.composing:
            self._backspace_block()
            self._pop_history()
            return True
        # 2) 조합중 블록이 없으면 확정 문자열에서 한 글자 제거
        if self._committed:
            self._committed = self._committed[:-1]
            self._pop_history()
            return True
        return False

    def _pop_history(self) -> None:
        if self._history:
            self._history.pop()

    def _backspace_block(self) -> None:
        """조합중 블록을 자모 한 단계 되돌린다."""
        # 종성이 있으면 종성부터 제거
        if self._jong:
            split = _JONG_SPLIT.get(self._jong)
            if split is not None:
                # 겹받침 -> 앞자음만 남김
                self._jong = split[0]
            else:
                self._jong = ""
            return
        # 종성이 없고 중성이 있으면 중성 제거(겹모음은 한 단계 분해)
        if self._jung is not None:
            split = _VOWEL_SPLIT.get(self._jung)
            if split is not None:
                self._jung = split[0]
            else:
                self._jung = None
            return
        # 중성이 없고 초성만 있으면 초성 제거
        if self._cho is not None:
            self._cho = None

    def flush(self) -> str:
        """현재까지 조합 확정 문자열을 반환하고 내부를 비운다."""
        result = self.text
        self.reset()
        return result


# ---------------------------------------------------------------------------
# 조합키 / 특수키 표시 토큰 헬퍼
# ---------------------------------------------------------------------------
# 수식어(모디파이어) 표시 순서와 이름
_MOD_ORDER = ["ctrl", "alt", "shift", "win"]
_MOD_LABEL = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "win": "Win", "cmd": "Win"}

# 특수키 raw 이름 -> 표시 토큰
_SPECIAL_NAMES = {
    "enter": "Enter",
    "return": "Enter",
    "tab": "Tab",
    "esc": "Esc",
    "escape": "Esc",
    "space": "Space",
    "backspace": "Backspace",
    "left": "←",
    "right": "→",
    "up": "↑",
    "down": "↓",
    "delete": "Del",
    "del": "Del",
    "home": "Home",
    "end": "End",
    "page_up": "PgUp",
    "pageup": "PgUp",
    "page_down": "PgDn",
    "pagedown": "PgDn",
    "caps_lock": "CapsLk",
    "capslock": "CapsLk",
    "insert": "Ins",
    "cmd": "Win",
    "win": "Win",
}


def combo_label(mods: list[str], key: str) -> str:
    """수식어 목록과 키를 조합 토큰 문자열로 만든다.

    예) (['ctrl','alt'], 'C') -> 'Ctrl + Alt + C'
    표시 순서는 Ctrl, Alt, Shift, Win 으로 정규화한다.
    """
    seen = {m.lower() for m in mods}
    parts: list[str] = []
    for m in _MOD_ORDER:
        # cmd 는 win 으로 정규화되므로 별도 처리
        if m in seen or (m == "win" and "cmd" in seen):
            parts.append(_MOD_LABEL[m])
    parts.append(key)
    return " + ".join(parts)


def special_name(raw: str) -> str:
    """특수키 raw 이름을 표시 토큰으로 변환한다.

    알 수 없는 값은 첫 글자만 대문자로 만든다.
    """
    key = raw.lower()
    if key in _SPECIAL_NAMES:
        return _SPECIAL_NAMES[key]
    if not raw:
        return raw
    return raw[:1].upper() + raw[1:]


class KeyCast:
    """최근 키 입력을 누적해 화면에 표시하는 버퍼.

    확정 문자열(_committed)과 조합중 한글 블록(HangulAutomaton)을 합쳐
    표시한다. 마지막 입력 후 duration 초가 지나면 만료되어 빈 문자열을 반환한다.
    """

    def __init__(
        self,
        *,
        duration: float = 1.5,
        max_len: int = 40,
        hangul: bool = False,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        self._duration = duration
        self._max_len = max_len
        self._hangul = hangul
        self._clock: Callable[[], float] = clock or time.monotonic
        self._committed: str = ""
        self._auto = HangulAutomaton()
        self._last_input_time: Optional[float] = None

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------
    def _expired(self) -> bool:
        """마지막 입력 후 duration 초가 지났으면 True."""
        if self._last_input_time is None:
            return True
        return (self._clock() - self._last_input_time) > self._duration

    def _ensure_fresh(self) -> None:
        """만료 상태였다면 새 입력 전에 버퍼를 초기화한다."""
        if self._expired():
            self._committed = ""
            self._auto.reset()

    def _touch(self) -> None:
        """마지막 입력 시각을 갱신한다."""
        self._last_input_time = self._clock()

    def _flush_auto(self) -> None:
        """조합중 한글 블록을 확정해 _committed 로 옮긴다."""
        if self._auto.composing:
            self._committed += self._auto.flush()

    def _trim(self) -> None:
        """표시 길이가 max_len 을 넘으면 앞에서 잘라낸다.

        조합중 블록 길이를 고려해 확정분을 우선 잘라낸다.
        """
        composing = self._auto.text
        overflow = len(self._committed) + len(composing) - self._max_len
        if overflow > 0:
            # 확정분에서 앞부분을 잘라낸다(조합중 블록은 가능한 보존)
            if overflow >= len(self._committed):
                self._committed = ""
            else:
                self._committed = self._committed[overflow:]

    # ------------------------------------------------------------------
    # 입력 API
    # ------------------------------------------------------------------
    def feed_char(self, ch: str) -> None:
        """출력 문자 1글자(영문/숫자/기호)를 입력한다.

        한글 모드이고 ch 가 두벌식 매핑에 있으면 자모로 조합하고,
        아니면 조합을 flush 한 뒤 ch 를 그대로 덧붙인다.
        """
        self._ensure_fresh()
        if self._hangul and ch in QWERTY_TO_JAMO:
            self._auto.feed(QWERTY_TO_JAMO[ch])
        else:
            self._flush_auto()
            self._committed += ch
        self._trim()
        self._touch()

    def feed_space(self) -> None:
        """공백 ' ' 을 덧붙인다(조합 flush)."""
        self._ensure_fresh()
        self._flush_auto()
        self._committed += " "
        self._trim()
        self._touch()

    def feed_special(self, raw_name: str) -> None:
        """특수키를 표시 토큰으로 변환해 덧붙인다(조합 flush).

        'enter' 는 현재 줄을 비우고 새 줄을 시작한다.
        'space' 는 공백을 덧붙인다.
        """
        self._ensure_fresh()
        key = raw_name.lower()
        if key in ("enter", "return"):
            # 새 줄 시작: 전체 라인을 비운다.
            self._auto.reset()
            self._committed = ""
            self._touch()
            return
        self._flush_auto()
        if key == "space":
            self._committed += " "
        else:
            self._committed += special_name(raw_name)
        self._trim()
        self._touch()

    def feed_combo(self, label: str) -> None:
        """조합 토큰(예: 'Ctrl + Alt + C')을 덧붙인다(조합 flush)."""
        self._ensure_fresh()
        self._flush_auto()
        self._committed += label
        self._trim()
        self._touch()

    def backspace(self) -> None:
        """조합중이면 자모 단위로, 아니면 마지막 글자를 삭제한다."""
        self._ensure_fresh()
        if self._auto.composing:
            self._auto.backspace()
        elif self._committed:
            self._committed = self._committed[:-1]
        self._touch()

    # ------------------------------------------------------------------
    # 한글 토글
    # ------------------------------------------------------------------
    def set_hangul(self, on: bool) -> None:
        """한글 모드를 설정한다. 모드 전환 시 조합중 블록은 확정한다."""
        if on != self._hangul:
            self._flush_auto()
        self._hangul = on

    def toggle_hangul(self) -> None:
        self.set_hangul(not self._hangul)

    @property
    def hangul(self) -> bool:
        return self._hangul

    # ------------------------------------------------------------------
    # 표시
    # ------------------------------------------------------------------
    def text(self) -> str:
        """화면에 표시할 문자열(확정분 + 조합중). 만료되면 '' 반환."""
        if self._expired():
            return ""
        return self._committed + self._auto.text

    def is_active(self) -> bool:
        """text() 가 비어있지 않고 만료 전이면 True."""
        return bool(self.text())

