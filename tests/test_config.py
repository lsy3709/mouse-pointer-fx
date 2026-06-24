"""config 모듈 단위 테스트."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mousepointerfx import config  # noqa: E402


def test_default_config_has_sections():
    cfg = config.default_config()
    assert set(cfg.keys()) == {"pointer", "click", "laser", "keycast", "general"}
    assert cfg["pointer"]["style"] == "laser"
    assert cfg["pointer"]["color"] == "#FF2D2D"


def test_keycast_defaults():
    cfg = config.default_config()
    assert cfg["keycast"]["color"] == "#FFFFFF"
    assert cfg["keycast"]["start_active"] is False
    # 옛 설정도 병합 시 keycast 섹션이 채워져야 함
    merged = config.merge_defaults({"pointer": {"size": 10}})
    assert "keycast" in merged and merged["keycast"]["font_size"] == 44


def test_default_config_is_deep_copy():
    a = config.default_config()
    a["pointer"]["size"] = 999
    b = config.default_config()
    assert b["pointer"]["size"] != 999


def test_laser_start_active_default_false():
    cfg = config.default_config()
    assert cfg["laser"]["start_active"] is False     # 코드 기본은 꺼짐(보수적)


def test_merge_fills_start_active_for_old_configs():
    # start_active 키가 없던 옛 설정도 병합 시 기본값으로 채워져야 함
    merged = config.merge_defaults({"laser": {"hotkey": "<f8>"}})
    assert merged["laser"]["hotkey"] == "<f8>"
    assert merged["laser"]["start_active"] is False


def test_merge_fills_missing_keys():
    merged = config.merge_defaults({"pointer": {"size": 50}})
    assert merged["pointer"]["size"] == 50          # 사용자 값 유지
    assert merged["pointer"]["style"] == "laser"    # 누락 키 기본값
    assert "click" in merged                          # 누락 섹션 기본값


def test_merge_ignores_unknown_keys():
    merged = config.merge_defaults({"bogus": 1, "pointer": {"nope": 2, "size": 10}})
    assert "bogus" not in merged
    assert "nope" not in merged["pointer"]
    assert merged["pointer"]["size"] == 10


def test_merge_rejects_wrong_type():
    # 손상된 타입은 기본값으로 대체
    merged = config.merge_defaults({"pointer": {"size": "huge"}})
    assert merged["pointer"]["size"] == config.DEFAULT_CONFIG["pointer"]["size"]


def test_load_missing_file_returns_default(tmp_path):
    p = str(tmp_path / "none.json")
    assert config.load(p) == config.default_config()


def test_load_corrupt_file_returns_default(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{ not valid json ", encoding="utf-8")
    assert config.load(str(p)) == config.default_config()


def test_save_then_load_roundtrip(tmp_path):
    p = str(tmp_path / "sub" / "config.json")  # 부모 폴더 자동 생성
    cfg = config.default_config()
    cfg["pointer"]["color"] = "#00FF00"
    cfg["laser"]["dot_size"] = 33
    config.save(cfg, p)
    assert os.path.exists(p)
    loaded = config.load(p)
    assert loaded["pointer"]["color"] == "#00FF00"
    assert loaded["laser"]["dot_size"] == 33


def test_saved_file_is_valid_json(tmp_path):
    p = str(tmp_path / "c.json")
    config.save(config.default_config(), p)
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    assert data["pointer"]["style"] == "laser"
