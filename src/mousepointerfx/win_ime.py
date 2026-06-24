"""포그라운드 창의 한글 IME(한/영) 상태 조회 (Win32 ctypes).

키 입력 표시(keycast)에서 한글 조합 모드를 OS IME 상태와 자동 동기화하기 위함.
pynput 은 물리키의 영문 글자만 주므로, 실제로 한글 입력 중인지(IME native 모드)는
이 함수로 따로 알아내야 한다.

WM_IME_CONTROL(IMC_GETCONVERSIONMODE) 를 포그라운드 창의 기본 IME 창에 보내
IME_CMODE_NATIVE 비트를 확인한다. SendMessageTimeout 으로 호출해 행(hang) 방지.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_imm32 = ctypes.WinDLL("imm32", use_last_error=True)

_WM_IME_CONTROL = 0x0283
_IMC_GETCONVERSIONMODE = 0x0001
_IME_CMODE_NATIVE = 0x0001
_SMTO_ABORTIFHUNG = 0x0002

_user32.GetForegroundWindow.restype = wintypes.HWND
_imm32.ImmGetDefaultIMEWnd.restype = wintypes.HWND
_imm32.ImmGetDefaultIMEWnd.argtypes = [wintypes.HWND]
_user32.SendMessageTimeoutW.restype = wintypes.LPARAM
_user32.SendMessageTimeoutW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
    wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t),
]


def foreground_hangul_state():
    """포그라운드 창 IME 가 한글(native) 모드면 True, 영문이면 False, 알 수 없으면 None."""
    try:
        hwnd = _user32.GetForegroundWindow()
        if not hwnd:
            return None
        hime = _imm32.ImmGetDefaultIMEWnd(hwnd)
        if not hime:
            return None
        result = ctypes.c_size_t(0)
        ok = _user32.SendMessageTimeoutW(
            hime, _WM_IME_CONTROL, _IMC_GETCONVERSIONMODE, 0,
            _SMTO_ABORTIFHUNG, 80, ctypes.byref(result))
        if not ok:
            return None
        return bool(result.value & _IME_CMODE_NATIVE)
    except Exception:
        return None
