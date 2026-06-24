"""데모 GIF 녹화기 → docs/demo.gif.

깔끔한 어두운 배경(실제 바탕화면 비노출) 위에서 레이저/클릭/키입력 데모를 자동 재생하며
기본 모니터를 캡처해 GIF로 저장한다. 끝나면(예외 포함) 시스템 커서를 복원한다.

실행: python tools/record_demo.py
"""
import math
import os
import sys
import time

os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_SCALE_FACTOR"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import ctypes  # noqa: E402

import win32api  # noqa: E402
from PIL import Image, ImageGrab  # noqa: E402
from PyQt6.QtCore import Qt, QTimer  # noqa: E402
from PyQt6.QtGui import QColor, QFont, QPainter  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402

from mousepointerfx import config as cfg_mod  # noqa: E402
from mousepointerfx import win_cursor  # noqa: E402
from mousepointerfx.overlay import Overlay  # noqa: E402

TOTAL = 7.6           # 전체 길이(초)
FPS = 10
TARGET_W = 760        # GIF 가로 px
COLORS = 128


class Backdrop(QWidget):
    def __init__(self, w, h):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setGeometry(0, 0, w, h)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#0d1117"))
        p.setPen(QColor(255, 255, 255, 38))
        f = QFont(); f.setPointSize(40); f.setBold(True); p.setFont(f)
        p.drawText(self.rect().adjusted(0, 60, 0, 0),
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, "Mouse Pointer FX")
        f2 = QFont(); f2.setPointSize(15); p.setFont(f2); p.setPen(QColor(255, 255, 255, 28))
        p.drawText(self.rect().adjusted(0, 132, 0, 0),
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                   "laser pointer · click effects · keystroke display")
        p.end()


def _set_dpi_aware():
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)); return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def main():
    _set_dpi_aware()
    app = QApplication(sys.argv)
    sw = win32api.GetSystemMetrics(0)
    sh = win32api.GetSystemMetrics(1)

    backdrop = Backdrop(sw, sh)
    backdrop.show()

    cfg = cfg_mod.default_config()
    cfg["laser"]["dot_size"] = 22
    cfg["laser"]["trail_length_ms"] = 450
    cfg["keycast"]["font_size"] = 48
    cfg["keycast"]["duration_ms"] = 3500
    cfg["click"]["size"] = 95
    ov = Overlay(cfg)
    ov.show(); ov.raise_()
    ov.set_laser(True)
    ov.set_keycast(True)
    win_cursor.hide_system_cursor()

    frames = []
    bbox = (0, 0, sw, sh)
    start = time.monotonic()
    kc = ov.keycast

    events = []

    def add(t, fn):
        events.append([t, fn, False])

    add(1.1, lambda: ov.on_click(int(sw * 0.30), int(sh * 0.42), "left"))
    add(2.1, lambda: ov.on_click(int(sw * 0.52), int(sh * 0.58), "right"))
    add(3.1, lambda: ov.on_click(int(sw * 0.70), int(sh * 0.40), "left"))
    add(3.7, lambda: kc.set_hangul(False))
    for i, ch in enumerate("Hello"):
        add(3.8 + i * 0.12, (lambda c: (lambda: kc.feed_char(c)))(ch))
    add(4.5, lambda: kc.feed_space())
    add(4.6, lambda: kc.set_hangul(True))
    for i, ch in enumerate("dkssud"):   # 두벌식 → 안녕
        add(4.7 + i * 0.14, (lambda c: (lambda: kc.feed_char(c)))(ch))
    add(5.7, lambda: kc.set_hangul(False))
    add(5.8, lambda: kc.feed_space())
    add(5.9, lambda: kc.feed_combo("Ctrl + C"))

    def drive():
        t = time.monotonic() - start
        mx0, mx1 = sw * 0.13, sw * 0.84
        x = mx0 + (mx1 - mx0) * min(1.0, t / 6.2)
        y = sh * 0.5 + sh * 0.14 * math.sin(t * 1.6)
        try:
            win32api.SetCursorPos((int(x), int(y)))
        except Exception:
            pass
        for ev in events:
            if not ev[2] and t >= ev[0]:
                ev[2] = True
                try:
                    ev[1]()
                except Exception:
                    pass

    def capture():
        try:
            img = ImageGrab.grab(bbox=bbox)
            if img.width > TARGET_W:
                h = int(img.height * TARGET_W / img.width)
                img = img.resize((TARGET_W, h), Image.LANCZOS)
            frames.append(img.convert("RGB"))
        except Exception:
            pass

    driver = QTimer(); driver.timeout.connect(drive); driver.start(16)
    cap = QTimer(); cap.timeout.connect(capture); cap.start(int(1000 / FPS))

    def finish():
        driver.stop(); cap.stop()
        ov.hide(); backdrop.hide()
        win_cursor.restore_system_cursor()
        app.quit()

    QTimer.singleShot(int(TOTAL * 1000), finish)
    app.exec()

    if not frames:
        print("no frames captured")
        return 1
    out = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "..", "docs", "demo.gif"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    pal = [f.convert("P", palette=Image.ADAPTIVE, colors=COLORS) for f in frames]
    pal[0].save(out, save_all=True, append_images=pal[1:],
                duration=int(1000 / FPS), loop=0, optimize=True, disposal=2)
    print(f"saved {out}  frames={len(frames)}  size={os.path.getsize(out)} bytes "
          f"({os.path.getsize(out)/1024/1024:.2f} MB)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        try:
            win_cursor.restore_system_cursor()
        except Exception:
            pass
