"""레이저 점 아이콘(assets/icon.ico, icon.png) 생성.

트레이 아이콘과 동일한 모양(파워포인트형 빨간 레이저 점)을 파일로 굽는다.
바탕화면 바로가기 / .exe 빌드에서 사용.
"""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtGui import QPainter, QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from mousepointerfx import cursor_renderer as render  # noqa: E402


def main() -> int:
    QApplication(sys.argv)
    assets = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
    os.makedirs(assets, exist_ok=True)

    pm = QPixmap(256, 256)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    render.draw_laser_dot(p, 128, 128, "#FF2D2D", 200, glow=True, opacity=100)
    p.end()

    ico = os.path.abspath(os.path.join(assets, "icon.ico"))
    png = os.path.abspath(os.path.join(assets, "icon.png"))
    ok_ico = pm.save(ico, "ICO")
    ok_png = pm.save(png, "PNG")
    print(f"icon.ico: {ok_ico} ({ico})")
    print(f"icon.png: {ok_png} ({png})")
    return 0 if ok_ico else 1


if __name__ == "__main__":
    raise SystemExit(main())
