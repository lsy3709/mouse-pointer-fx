"""Mouse Pointer FX 진입점.

Qt 고DPI 스케일을 1로 고정해 GetCursorPos(물리 px)와 좌표를 1:1로 맞춘다.
이 설정은 QApplication 생성 전에 적용돼야 하므로 import 보다 먼저 둔다.

pythonw(콘솔 없음)로 실행될 때 시작 중 예외가 나면 조용히 죽지 않도록
메시지박스 + 로그(%APPDATA%\\MousePointerFX\\error.log)로 알리고,
어떤 경우에도 시스템 커서를 복원한다.
"""
import os
import sys
import traceback

os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_SCALE_FACTOR"] = "1"

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))


def _show_error(message: str) -> None:
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            None, message, "Mouse Pointer FX - 오류", 0x10)
    except Exception:
        pass


def _write_log(text: str) -> None:
    try:
        logdir = os.path.join(os.environ.get("APPDATA", ""), "MousePointerFX")
        os.makedirs(logdir, exist_ok=True)
        with open(os.path.join(logdir, "error.log"), "w", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        pass


def _safe_restore_cursor() -> None:
    try:
        from mousepointerfx import win_cursor
        win_cursor.restore_system_cursor()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        from mousepointerfx.app import main
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        tb = traceback.format_exc()
        _write_log(tb)
        _safe_restore_cursor()
        _show_error("시작 중 오류가 발생했습니다.\n\n" + tb[-1500:])
        raise SystemExit(1)
