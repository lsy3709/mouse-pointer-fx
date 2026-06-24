"""keycast 모듈 단위 테스트(헤드리스, PyQt 불필요)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mousepointerfx import keycast  # noqa: E402
from mousepointerfx.keycast import (  # noqa: E402
    HangulAutomaton,
    KeyCast,
    QWERTY_TO_JAMO,
    combo_label,
    special_name,
)


# ---------------------------------------------------------------------------
# 테스트용 제어 가능한 시계(클로저 홀더)
# ---------------------------------------------------------------------------
class FakeClock:
    """수동으로 시간을 진행시킬 수 있는 시계."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def set(self, t: float) -> None:
        self.now = t

    def advance(self, dt: float) -> None:
        self.now += dt


def feed_jamo(auto: HangulAutomaton, *jamos: str) -> None:
    for j in jamos:
        auto.feed(j)


def type_keys(kc: KeyCast, keys: str) -> None:
    """QWERTY 문자열을 한 글자씩 feed_char 로 입력."""
    for ch in keys:
        kc.feed_char(ch)


# ---------------------------------------------------------------------------
# QWERTY_TO_JAMO 매핑 계약
# ---------------------------------------------------------------------------
def test_qwerty_map_required_consonants():
    expected = {
        "r": "ㄱ", "R": "ㄲ", "s": "ㄴ", "e": "ㄷ", "E": "ㄸ",
        "f": "ㄹ", "a": "ㅁ", "q": "ㅂ", "Q": "ㅃ", "t": "ㅅ",
        "T": "ㅆ", "d": "ㅇ", "w": "ㅈ", "W": "ㅉ", "c": "ㅊ",
        "z": "ㅋ", "x": "ㅌ", "v": "ㅍ", "g": "ㅎ",
    }
    for k, v in expected.items():
        assert QWERTY_TO_JAMO[k] == v


def test_qwerty_map_required_vowels():
    expected = {
        "k": "ㅏ", "o": "ㅐ", "i": "ㅑ", "O": "ㅒ", "j": "ㅓ",
        "p": "ㅔ", "u": "ㅕ", "P": "ㅖ", "h": "ㅗ", "y": "ㅛ",
        "n": "ㅜ", "b": "ㅠ", "m": "ㅡ", "l": "ㅣ",
    }
    for k, v in expected.items():
        assert QWERTY_TO_JAMO[k] == v


# ---------------------------------------------------------------------------
# HangulAutomaton 조합
# ---------------------------------------------------------------------------
def test_compose_han():
    """ㅎ,ㅏ,ㄴ -> '한'."""
    a = HangulAutomaton()
    feed_jamo(a, "ㅎ", "ㅏ", "ㄴ")
    assert a.text == "한"


def test_compose_annyeong_final_split():
    """ㅇ,ㅏ,ㄴ,ㄴ,ㅕ,ㅇ -> '안녕' (받침 분리)."""
    a = HangulAutomaton()
    feed_jamo(a, "ㅇ", "ㅏ", "ㄴ", "ㄴ", "ㅕ", "ㅇ")
    assert a.text == "안녕"


def test_compose_gama_final_move():
    """ㄱ,ㅏ,ㅁ,ㅏ -> '가마' (받침 이동)."""
    a = HangulAutomaton()
    feed_jamo(a, "ㄱ", "ㅏ", "ㅁ", "ㅏ")
    assert a.text == "가마"


def test_compose_dak_double_final():
    """ㄷ,ㅏ,ㄹ,ㄱ -> '닭' (겹받침 ㄺ)."""
    a = HangulAutomaton()
    feed_jamo(a, "ㄷ", "ㅏ", "ㄹ", "ㄱ")
    assert a.text == "닭"


def test_compose_gwa_compound_vowel():
    """ㄱ,ㅗ,ㅏ -> '과' (겹모음 ㅘ)."""
    a = HangulAutomaton()
    feed_jamo(a, "ㄱ", "ㅗ", "ㅏ")
    assert a.text == "과"


def test_compose_all_compound_vowels():
    cases = {
        ("ㅗ", "ㅏ"): "ㅘ",
        ("ㅗ", "ㅐ"): "ㅙ",
        ("ㅗ", "ㅣ"): "ㅚ",
        ("ㅜ", "ㅓ"): "ㅝ",
        ("ㅜ", "ㅔ"): "ㅞ",
        ("ㅜ", "ㅣ"): "ㅟ",
        ("ㅡ", "ㅣ"): "ㅢ",
    }
    for (v1, v2), combined in cases.items():
        a = HangulAutomaton()
        feed_jamo(a, "ㅇ", v1, v2)
        # ㅇ + 겹모음 = 단일 음절
        assert len(a.text) == 1
        # 같은 겹모음을 직접 만든 음절과 일치
        b = HangulAutomaton()
        feed_jamo(b, "ㅇ", combined)
        assert a.text == b.text


def test_compose_double_finals():
    """대표 겹받침들이 단일 음절로 합쳐지는지."""
    cases = {
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
    for (c1, c2), _name in cases.items():
        a = HangulAutomaton()
        feed_jamo(a, "ㅇ", "ㅏ", c1, c2)
        assert len(a.text) == 1  # 한 음절로 합쳐짐(겹받침)


def test_compose_double_consonants():
    """ㄲㄸㅃㅆㅉ 쌍자음 초성."""
    a = HangulAutomaton()
    feed_jamo(a, "ㄲ", "ㅏ")
    assert a.text == "까"
    a.reset()
    feed_jamo(a, "ㅆ", "ㅏ")
    assert a.text == "싸"
    a.reset()
    feed_jamo(a, "ㅉ", "ㅏ")
    assert a.text == "짜"


def test_two_consonants_in_a_row():
    """초성만 있는 상태에서 자음 또 입력 -> 앞 초성 확정."""
    a = HangulAutomaton()
    feed_jamo(a, "ㄱ", "ㄴ")
    assert a.text == "ㄱㄴ"


def test_double_final_move_keeps_first():
    """겹받침 뒤 모음 -> 앞 자음은 받침으로 남고 뒷 자음만 이동."""
    a = HangulAutomaton()
    feed_jamo(a, "ㄷ", "ㅏ", "ㄹ", "ㄱ", "ㅏ")  # 닭 + ㅏ -> 달가
    assert a.text == "달가"


# ---------------------------------------------------------------------------
# backspace 분해
# ---------------------------------------------------------------------------
def test_backspace_decomposes_syllable():
    """'한' -> '하' -> 'ㅎ' -> '' 자모 단위 되돌림."""
    a = HangulAutomaton()
    feed_jamo(a, "ㅎ", "ㅏ", "ㄴ")
    assert a.text == "한"
    assert a.backspace() is True
    assert a.text == "하"
    assert a.backspace() is True
    assert a.text == "ㅎ"
    assert a.backspace() is True
    assert a.text == ""
    # 더 이상 되돌릴 게 없음
    assert a.backspace() is False


def test_backspace_compound_vowel():
    """겹모음 한 단계 분해: '과' -> '고' -> 'ㄱ'."""
    a = HangulAutomaton()
    feed_jamo(a, "ㄱ", "ㅗ", "ㅏ")
    assert a.text == "과"
    a.backspace()
    assert a.text == "고"
    a.backspace()
    assert a.text == "ㄱ"


def test_backspace_double_final():
    """겹받침 한 단계 분해: '닭' -> '달'."""
    a = HangulAutomaton()
    feed_jamo(a, "ㄷ", "ㅏ", "ㄹ", "ㄱ")
    assert a.text == "닭"
    a.backspace()
    assert a.text == "달"


def test_flush_clears_and_returns():
    a = HangulAutomaton()
    feed_jamo(a, "ㅎ", "ㅏ", "ㄴ")
    assert a.flush() == "한"
    assert a.text == ""
    assert a.composing is False


# ---------------------------------------------------------------------------
# KeyCast: 영문/한글 입력
# ---------------------------------------------------------------------------
def test_keycast_english_abc():
    clk = FakeClock()
    kc = KeyCast(duration=1.0, clock=clk)
    type_keys(kc, "abc")
    assert kc.text() == "abc"


def test_keycast_hangul_compose():
    """한글 모드에서 g,k,s [ㅎㅏㄴ] -> '한'."""
    clk = FakeClock()
    kc = KeyCast(duration=1.0, hangul=True, clock=clk)
    kc.feed_char("g")  # ㅎ
    kc.feed_char("k")  # ㅏ
    kc.feed_char("s")  # ㄴ
    assert kc.text() == "한"


def test_keycast_hangul_word():
    """한글 모드: dkssud [ㅇㅏㄴㄴㅕㅇ] -> '안녕'."""
    clk = FakeClock()
    kc = KeyCast(duration=10.0, hangul=True, clock=clk)
    for ch in "dkssud":
        kc.feed_char(ch)
    assert kc.text() == "안녕"


def test_keycast_non_jamo_in_hangul_flushes():
    """한글 모드에서 매핑에 없는 문자는 조합 flush 후 그대로 덧붙임."""
    clk = FakeClock()
    kc = KeyCast(duration=10.0, hangul=True, clock=clk)
    kc.feed_char("g")  # ㅎ
    kc.feed_char("k")  # ㅏ -> 하
    kc.feed_char("1")  # 비자모 -> flush('하') + '1'
    assert kc.text() == "하1"


# ---------------------------------------------------------------------------
# KeyCast: 만료(expiry) — 주입 시계로 결정론적 검증
# ---------------------------------------------------------------------------
def test_keycast_expiry():
    clk = FakeClock(start=0.0)
    kc = KeyCast(duration=1.0, clock=clk)
    type_keys(kc, "abc")          # t=0 에 입력
    assert kc.text() == "abc"

    clk.set(0.5)                  # 만료 전
    assert kc.text() == "abc"
    assert kc.is_active() is True

    clk.set(2.0)                  # 만료 후(duration=1.0 초과)
    assert kc.text() == ""
    assert kc.is_active() is False


def test_keycast_expiry_boundary():
    """경계: 정확히 duration 일 때는 아직 살아있고, 초과 시 만료."""
    clk = FakeClock(start=0.0)
    kc = KeyCast(duration=1.0, clock=clk)
    kc.feed_char("a")
    clk.set(1.0)                  # now - last == duration -> 만료 아님
    assert kc.text() == "a"
    clk.set(1.0001)               # 초과 -> 만료
    assert kc.text() == ""


def test_keycast_fresh_after_expiry():
    """만료 후 새 입력은 깨끗한 상태에서 시작."""
    clk = FakeClock(start=0.0)
    kc = KeyCast(duration=1.0, clock=clk)
    type_keys(kc, "old")
    clk.set(5.0)                  # 만료
    assert kc.text() == ""
    kc.feed_char("x")             # 새 입력
    assert kc.text() == "x"       # 이전 'old' 가 남아있지 않음


# ---------------------------------------------------------------------------
# KeyCast: max_len
# ---------------------------------------------------------------------------
def test_keycast_max_len():
    clk = FakeClock()
    kc = KeyCast(duration=100.0, max_len=5, clock=clk)
    type_keys(kc, "abcdefghij")   # 10글자 입력
    txt = kc.text()
    assert len(txt) == 5
    assert txt == "fghij"         # 마지막 5글자만 유지(앞에서 잘림)


def test_keycast_max_len_exact():
    clk = FakeClock()
    kc = KeyCast(duration=100.0, max_len=3, clock=clk)
    type_keys(kc, "xyz")
    assert kc.text() == "xyz"
    kc.feed_char("w")
    assert kc.text() == "yzw"


# ---------------------------------------------------------------------------
# KeyCast: 공백 / 특수키 / 조합키
# ---------------------------------------------------------------------------
def test_keycast_space():
    clk = FakeClock()
    kc = KeyCast(duration=100.0, clock=clk)
    type_keys(kc, "hi")
    kc.feed_space()
    type_keys(kc, "yo")
    assert kc.text() == "hi yo"


def test_keycast_special_token():
    clk = FakeClock()
    kc = KeyCast(duration=100.0, clock=clk)
    type_keys(kc, "ab")
    kc.feed_special("tab")
    assert kc.text() == "abTab"
    kc.feed_special("left")
    assert kc.text() == "abTab←"


def test_keycast_special_flushes_hangul():
    """특수키 입력 시 조합중 한글은 확정된다."""
    clk = FakeClock()
    kc = KeyCast(duration=100.0, hangul=True, clock=clk)
    kc.feed_char("g")  # ㅎ
    kc.feed_char("k")  # ㅏ -> 하(조합중)
    kc.feed_special("tab")
    assert kc.text() == "하Tab"


def test_keycast_enter_starts_new_line():
    """enter 는 현재 줄을 비우고 새 줄을 시작."""
    clk = FakeClock()
    kc = KeyCast(duration=100.0, clock=clk)
    type_keys(kc, "abc")
    kc.feed_special("enter")
    assert kc.text() == ""
    type_keys(kc, "xy")
    assert kc.text() == "xy"


def test_keycast_space_via_special():
    clk = FakeClock()
    kc = KeyCast(duration=100.0, clock=clk)
    type_keys(kc, "a")
    kc.feed_special("space")
    type_keys(kc, "b")
    assert kc.text() == "a b"


def test_keycast_combo():
    clk = FakeClock()
    kc = KeyCast(duration=100.0, clock=clk)
    type_keys(kc, "x")
    kc.feed_combo("Ctrl + C")
    assert kc.text() == "xCtrl + C"


def test_keycast_combo_flushes_hangul():
    clk = FakeClock()
    kc = KeyCast(duration=100.0, hangul=True, clock=clk)
    kc.feed_char("g")  # ㅎ
    kc.feed_char("k")  # ㅏ -> 하
    kc.feed_combo("Ctrl + V")
    assert kc.text() == "하Ctrl + V"


# ---------------------------------------------------------------------------
# KeyCast: backspace
# ---------------------------------------------------------------------------
def test_keycast_backspace_committed():
    clk = FakeClock()
    kc = KeyCast(duration=100.0, clock=clk)
    type_keys(kc, "abc")
    kc.backspace()
    assert kc.text() == "ab"


def test_keycast_backspace_jamo_level():
    """조합중일 때 backspace 는 자모 단위로 동작."""
    clk = FakeClock()
    kc = KeyCast(duration=100.0, hangul=True, clock=clk)
    kc.feed_char("g")  # ㅎ
    kc.feed_char("k")  # ㅏ
    kc.feed_char("s")  # ㄴ -> 한
    assert kc.text() == "한"
    kc.backspace()
    assert kc.text() == "하"
    kc.backspace()
    assert kc.text() == "ㅎ"


# ---------------------------------------------------------------------------
# KeyCast: 한글 토글
# ---------------------------------------------------------------------------
def test_keycast_toggle_hangul():
    clk = FakeClock()
    kc = KeyCast(duration=100.0, hangul=False, clock=clk)
    assert kc.hangul is False
    kc.toggle_hangul()
    assert kc.hangul is True
    kc.set_hangul(False)
    assert kc.hangul is False


def test_keycast_toggle_flushes_composition():
    """모드 전환 시 조합중 블록은 확정된다."""
    clk = FakeClock()
    kc = KeyCast(duration=100.0, hangul=True, clock=clk)
    kc.feed_char("g")  # ㅎ
    kc.feed_char("k")  # ㅏ -> 하(조합중)
    kc.set_hangul(False)
    type_keys(kc, "a")
    assert kc.text() == "하a"


# ---------------------------------------------------------------------------
# combo_label / special_name 헬퍼
# ---------------------------------------------------------------------------
def test_combo_label_basic():
    assert combo_label(["ctrl", "alt"], "C") == "Ctrl + Alt + C"


def test_combo_label_order_normalized():
    """입력 순서와 무관하게 Ctrl, Alt, Shift, Win 순으로 정규화."""
    assert combo_label(["shift", "ctrl"], "A") == "Ctrl + Shift + A"
    assert combo_label(["win", "alt", "ctrl", "shift"], "X") == "Ctrl + Alt + Shift + Win + X"


def test_combo_label_cmd_is_win():
    assert combo_label(["cmd"], "Q") == "Win + Q"


def test_combo_label_no_mods():
    assert combo_label([], "F5") == "F5"


def test_special_name_known():
    assert special_name("enter") == "Enter"
    assert special_name("return") == "Enter"
    assert special_name("tab") == "Tab"
    assert special_name("esc") == "Esc"
    assert special_name("space") == "Space"
    assert special_name("backspace") == "Backspace"
    assert special_name("left") == "←"
    assert special_name("right") == "→"
    assert special_name("up") == "↑"
    assert special_name("down") == "↓"
    assert special_name("f5") == "F5"
    assert special_name("delete") == "Del"
    assert special_name("home") == "Home"
    assert special_name("end") == "End"
    assert special_name("page_up") == "PgUp"
    assert special_name("page_down") == "PgDn"
    assert special_name("caps_lock") == "CapsLk"
    assert special_name("cmd") == "Win"
    assert special_name("win") == "Win"


def test_special_name_unknown_capitalized():
    """모르는 값은 첫 글자만 대문자."""
    assert special_name("foo") == "Foo"
    assert special_name("numlock") == "Numlock"


def test_keycast_default_clock_is_monotonic():
    """clock 미주입 시 time.monotonic 사용(스모크)."""
    kc = KeyCast(duration=100.0)
    kc.feed_char("a")
    assert kc.text() == "a"
    assert kc._clock is keycast.time.monotonic
