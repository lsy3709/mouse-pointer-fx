"""설정 로드/저장 + 기본값.

PyQt 등 무거운 의존성을 import 하지 않는 순수 로직 모듈(단위 테스트 대상).
설정은 %APPDATA%/MousePointerFX/config.json 에 저장된다.
"""
from __future__ import annotations

import copy
import json
import os
from typing import Any

APP_NAME = "MousePointerFX"

# 포인터 모양 목록(설정 콤보에서 사용)
POINTER_STYLES = ["laser", "dot", "ring", "circle", "cross", "arrow"]
# 클릭 효과 스타일 목록
CLICK_STYLES = ["ripple", "rings", "burst", "highlight"]

DEFAULT_CONFIG: dict[str, Any] = {
    "pointer": {
        "enabled": True,
        "style": "laser",          # 기본: 파워포인트형 레이저 점
        "color": "#FF2D2D",        # 빨강
        "size": 28,                # 지름(px)
        "glow": True,              # 글로우(외곽 번짐)
        "outline": False,
        "outline_color": "#FFFFFF",
        "opacity": 100,            # 0-100
    },
    "click": {
        "enabled": True,
        "style": "ripple",
        "left_color": "#3DA5FF",
        "right_color": "#FF9B3D",
        "size": 60,                # 최대 지름(px)
        "duration_ms": 450,
        "thickness": 4,
    },
    "laser": {
        "hotkey": "<ctrl>+<alt>+l",
        "color": "#FF2D2D",
        "dot_size": 18,
        "trail": True,
        "trail_length_ms": 350,
        "glow": True,
        "start_active": False,     # 시작 시 레이저 포인터를 켠 상태로 띄울지
    },
    "keycast": {
        "hotkey": "<ctrl>+<alt>+k",   # 키 입력 표시 토글
        "font_size": 44,
        "color": "#FFFFFF",           # 흰색
        "duration_ms": 1500,          # 마지막 입력 후 사라지기까지
        "max_chars": 40,
        "hangul": False,              # 시작 시 한글 조합 모드(한/영 키로 토글됨)
        "position": "center",         # center | bottom
        "bold": True,
        "start_active": False,        # 시작 시 켠 상태로 띄울지
    },
    "general": {
        "hide_system_cursor": True,
        "start_with_windows": False,
        "update_hz": 120,
    },
}


def get_config_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_NAME)


def get_config_path() -> str:
    return os.path.join(get_config_dir(), "config.json")


def default_config() -> dict[str, Any]:
    """기본 설정의 깊은 복사본을 반환."""
    return copy.deepcopy(DEFAULT_CONFIG)


def merge_defaults(user: dict[str, Any], defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    """사용자 설정을 기본값 위에 깊은 병합. 누락 키는 기본값으로 채운다.

    기본값에 없는 임의 키는 무시(스키마 방어). 타입이 다르면 기본값을 따른다.
    """
    if defaults is None:
        defaults = DEFAULT_CONFIG
    result: dict[str, Any] = {}
    for key, dval in defaults.items():
        if isinstance(dval, dict):
            uval = user.get(key)
            result[key] = merge_defaults(uval if isinstance(uval, dict) else {}, dval)
        else:
            uval = user.get(key, dval)
            # 타입이 호환되지 않으면 기본값 사용(예: 손상된 값)
            if type(uval) is not type(dval) and not (
                isinstance(dval, float) and isinstance(uval, int)
            ):
                uval = dval
            result[key] = uval
    return result


def load(path: str | None = None) -> dict[str, Any]:
    """설정 로드. 파일이 없거나 손상되면 기본값을 반환."""
    if path is None:
        path = get_config_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return default_config()
        return merge_defaults(data)
    except (OSError, json.JSONDecodeError, ValueError):
        return default_config()


def save(cfg: dict[str, Any], path: str | None = None) -> None:
    """설정 저장(부모 폴더 자동 생성)."""
    if path is None:
        path = get_config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
