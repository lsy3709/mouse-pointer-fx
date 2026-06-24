"""실제 데스크톱에서 앱 전체 경로를 약 1.8초간 띄웠다 자동 종료하는 라이브 셀프테스트.

오버레이/트레이/후킹/커서 숨김·복원까지 실제로 실행해 시작 오류가 없는지 확인한다.
종료 시 + finally 에서 시스템 커서를 반드시 복원한다.
"""
import os
import sys
import traceback

os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_SCALE_FACTOR"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from mousepointerfx import app as appmod  # noqa: E402
from mousepointerfx import win_cursor  # noqa: E402


def main() -> int:
    appmod._set_dpi_aware()
    qapp = QApplication(sys.argv)
    qapp.setQuitOnLastWindowClosed(False)
    ctrl = appmod.Controller(qapp)
    print("controller constructed; laser/pointer/tray/hook started", flush=True)
    QTimer.singleShot(1800, qapp.quit)
    rc = qapp.exec()
    print("event loop returned rc =", rc, flush=True)
    return rc


if __name__ == "__main__":
    code = 0
    try:
        code = main()
    except BaseException:
        traceback.print_exc()
        code = 1
    finally:
        win_cursor.restore_system_cursor()
        print("cursor restored:", not win_cursor.is_hidden(), flush=True)
    print("LIVE SELFTEST DONE", flush=True)
    raise SystemExit(code)
