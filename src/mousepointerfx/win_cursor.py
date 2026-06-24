"""시스템 커서 숨김/복원 (Win32 ctypes).

숨김: 모든 시스템 커서를 빈(투명) 커서로 교체(SetSystemCursor).
복원: SystemParametersInfo(SPI_SETCURSORS) 로 레지스트리 기본 커서 재로딩.

** 복원은 반드시 보장돼야 한다. ** 호출 측에서 atexit / 예외 / 시그널 모두에
restore() 가 걸리도록 연결한다.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes

_user32 = ctypes.WinDLL("user32", use_last_error=True)

# 표준 시스템 커서 OCR_* 식별자
_OCR_IDS = [
    32512,  # NORMAL (arrow)
    32513,  # IBEAM
    32514,  # WAIT
    32515,  # CROSS
    32516,  # UP
    32640,  # SIZE
    32641,  # ICON
    32642,  # SIZENWSE
    32643,  # SIZENESW
    32644,  # SIZEWE
    32645,  # SIZENS
    32646,  # SIZEALL
    32648,  # NO
    32649,  # HAND
    32650,  # APPSTARTING
    32651,  # HELP
]

_SPI_SETCURSORS = 0x0057
_SPIF_SENDCHANGE = 0x02

_user32.CreateCursor.restype = wintypes.HANDLE
_user32.CreateCursor.argtypes = [
    wintypes.HINSTANCE, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
]
_user32.SetSystemCursor.restype = wintypes.BOOL
_user32.SetSystemCursor.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_user32.SystemParametersInfoW.restype = wintypes.BOOL
_user32.SystemParametersInfoW.argtypes = [
    wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT,
]

_hidden = False


def _make_blank_cursor() -> int:
    """32x32 완전 투명 커서 생성. SetSystemCursor 가 소유권을 가져가 파괴하므로
    교체할 커서마다 새로 만든다."""
    w = h = 32
    nbytes = w * h // 8           # 평면당 비트수/8
    and_plane = b"\xFF" * nbytes  # AND=1 → 투명
    xor_plane = b"\x00" * nbytes  # XOR=0 → 색 없음
    return _user32.CreateCursor(None, 0, 0, w, h, and_plane, xor_plane)


def hide_system_cursor() -> bool:
    """모든 시스템 커서를 투명 커서로 교체. 성공 시 True."""
    global _hidden
    ok = False
    for ocr in _OCR_IDS:
        hcur = _make_blank_cursor()
        if hcur and _user32.SetSystemCursor(hcur, ocr):
            ok = True
    _hidden = ok
    return ok


def restore_system_cursor() -> bool:
    """레지스트리의 기본 커서를 다시 로드해 원상복구."""
    global _hidden
    res = bool(_user32.SystemParametersInfoW(_SPI_SETCURSORS, 0, None, _SPIF_SENDCHANGE))
    _hidden = False
    return res


def is_hidden() -> bool:
    return _hidden
