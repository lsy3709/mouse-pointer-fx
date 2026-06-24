"""앱 조립 + 트레이 아이콘 + 생명주기/정리.

DPI 인지 설정 → 단일 인스턴스 → 오버레이/후킹/트레이 구성 → 정리(커서 복원) 보장.
"""
from __future__ import annotations

import atexit
import ctypes
import os
import signal
import sys

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from . import APP_NAME
from . import config as config_mod
from . import cursor_renderer as render
from . import win_cursor
from .input_hook import InputBridge, InputHook
from .overlay import Overlay
from .settings_window import SettingsWindow


def _set_dpi_aware() -> None:
    """Per-Monitor-V2 DPI 인지(가능하면). Qt 스케일은 run.py에서 1로 고정."""
    try:
        # PER_MONITOR_AWARE_V2 = -4
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_AWARE
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _single_instance() -> bool:
    """이미 실행 중이면 False. (전역 뮤텍스)"""
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW(None, False, "MousePointerFX_SingleInstance_Mutex")
    return kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


def _make_icon() -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    render.draw_laser_dot(p, 32, 32, "#FF2D2D", 42, glow=True, opacity=100)
    p.end()
    return QIcon(pm)


def _startup_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pyw):
        pyw = sys.executable
    run_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "run.py"))
    return f'"{pyw}" "{run_py}"'


def _set_autostart(enabled: bool) -> None:
    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                            winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE) as k:
            if enabled:
                winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, _startup_command())
            else:
                try:
                    winreg.DeleteValue(k, APP_NAME)
                except FileNotFoundError:
                    pass
    except OSError:
        pass


class Controller:
    def __init__(self, qapp: QApplication) -> None:
        self.qapp = qapp
        self.cfg = config_mod.load()
        self.settings_win: SettingsWindow | None = None

        self.overlay = Overlay(self.cfg)
        self.overlay.show()

        # 커서를 숨기기 전에 정리(복원) 경로를 먼저 등록 → 숨김 직후 크래시에도 복원 보장
        self._cleaned = False
        qapp.aboutToQuit.connect(self.cleanup)
        atexit.register(self.cleanup)

        self.bridge = InputBridge()
        self.bridge.clicked.connect(self._on_click)
        self.bridge.toggle_laser.connect(self.toggle_laser)
        self.bridge.toggle_keycast.connect(self.toggle_keycast)
        self.bridge.key_event.connect(self.overlay.feed_key)
        self.hook = InputHook(self.bridge, self.cfg["laser"]["hotkey"],
                              self.cfg["keycast"]["hotkey"])
        self.hook.start()

        self._build_tray()

        # 시작 시 레이저 포인터를 켠 상태로 띄우기(자동 시작 등에서 유용)
        if self.cfg["laser"].get("start_active", False):
            self.overlay.set_laser(True)
            self.act_laser.blockSignals(True)
            self.act_laser.setChecked(True)
            self.act_laser.blockSignals(False)

        # 시작 시 키 입력 표시를 켠 상태로
        if self.cfg["keycast"].get("start_active", False):
            self._set_keycast(True)

        self._refresh_cursor_hidden()
        _set_autostart(self.cfg["general"]["start_with_windows"])

    # -------------------------------------------------------------- 트레이
    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(_make_icon(), self.qapp)
        self.tray.setToolTip("Mouse Pointer FX")
        menu = QMenu()

        self.act_pointer = QAction("커스텀 포인터", menu, checkable=True)
        self.act_pointer.setChecked(self.cfg["pointer"]["enabled"])
        self.act_pointer.toggled.connect(self.toggle_pointer)
        menu.addAction(self.act_pointer)

        self.act_laser = QAction("레이저 포인터", menu, checkable=True)
        self.act_laser.setChecked(False)
        self.act_laser.toggled.connect(self._tray_laser)
        menu.addAction(self.act_laser)

        self.act_keycast = QAction("키 입력 표시", menu, checkable=True)
        self.act_keycast.setChecked(False)
        self.act_keycast.toggled.connect(self._tray_keycast)
        menu.addAction(self.act_keycast)

        menu.addSeparator()
        act_settings = QAction("설정…", menu)
        act_settings.triggered.connect(self.open_settings)
        menu.addAction(act_settings)

        act_quit = QAction("종료", menu)
        act_quit.triggered.connect(self.qapp.quit)
        menu.addAction(act_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()
        hk = self.cfg["laser"]["hotkey"]
        self.tray.showMessage(
            "Mouse Pointer FX 실행 중",
            f"레이저 토글: {hk}  ·  트레이 아이콘에서 설정/종료",
            _make_icon(), 4000,
        )

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.open_settings()

    # -------------------------------------------------------------- 동작
    def _on_click(self, x: int, y: int, button: str) -> None:
        self.overlay.on_click(x, y, button)

    def toggle_laser(self) -> None:
        self.overlay.set_laser(not self.overlay.laser_active)
        self.act_laser.blockSignals(True)
        self.act_laser.setChecked(self.overlay.laser_active)
        self.act_laser.blockSignals(False)
        self._refresh_cursor_hidden()

    def _tray_laser(self, checked: bool) -> None:
        if checked != self.overlay.laser_active:
            self.overlay.set_laser(checked)
            self._refresh_cursor_hidden()

    # ----- 키 입력 표시(keycast)
    def _set_keycast(self, on: bool) -> None:
        self.overlay.set_keycast(on)
        if on:
            self.hook.start_capture()
        else:
            self.hook.stop_capture()
        self.act_keycast.blockSignals(True)
        self.act_keycast.setChecked(on)
        self.act_keycast.blockSignals(False)

    def toggle_keycast(self) -> None:
        self._set_keycast(not self.overlay.keycast_active)

    def _tray_keycast(self, checked: bool) -> None:
        if checked != self.overlay.keycast_active:
            self._set_keycast(checked)

    def toggle_pointer(self, checked: bool) -> None:
        self.cfg["pointer"]["enabled"] = checked
        config_mod.save(self.cfg)
        self.overlay.apply_config(self.cfg)
        self._refresh_cursor_hidden()

    def open_settings(self) -> None:
        if self.settings_win is None:
            self.settings_win = SettingsWindow(self.cfg, self.on_config_change)
        self.settings_win.show()
        self.settings_win.raise_()
        self.settings_win.activateWindow()

    def on_config_change(self, cfg: dict) -> None:
        self.cfg = cfg
        config_mod.save(cfg)
        self.overlay.apply_config(cfg)
        self.hook.set_hotkey(cfg["laser"]["hotkey"])
        self.hook.set_keycast_hotkey(cfg["keycast"]["hotkey"])
        self.act_pointer.blockSignals(True)
        self.act_pointer.setChecked(cfg["pointer"]["enabled"])
        self.act_pointer.blockSignals(False)
        _set_autostart(cfg["general"]["start_with_windows"])
        self._refresh_cursor_hidden()

    def _refresh_cursor_hidden(self) -> None:
        want = self.cfg["general"]["hide_system_cursor"] and (
            self.cfg["pointer"]["enabled"] or self.overlay.laser_active)
        if want and not win_cursor.is_hidden():
            win_cursor.hide_system_cursor()
        elif not want and win_cursor.is_hidden():
            win_cursor.restore_system_cursor()

    def cleanup(self) -> None:
        if self._cleaned:
            return
        self._cleaned = True
        try:
            self.hook.stop()
        except Exception:
            pass
        win_cursor.restore_system_cursor()


def main() -> int:
    _set_dpi_aware()
    if not _single_instance():
        # 이미 실행 중
        app = QApplication(sys.argv)
        QMessageBox.information(None, APP_NAME, "이미 실행 중입니다. (트레이 아이콘 확인)")
        return 0

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 설정창 닫아도 트레이 상주

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.warning(None, APP_NAME, "시스템 트레이를 사용할 수 없습니다.")

    controller = Controller(app)

    # 커서 복원 보장: 어떤 종료 경로에서도
    def _sig(_signum, _frame):
        controller.cleanup()
        app.quit()

    try:
        signal.signal(signal.SIGINT, _sig)
        signal.signal(signal.SIGTERM, _sig)
    except Exception:
        pass
    # Qt 이벤트 루프 중에도 파이썬 시그널이 처리되도록 주기적 깨우기
    _wake = QTimer()
    _wake.start(250)
    _wake.timeout.connect(lambda: None)

    try:
        return app.exec()
    finally:
        controller.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
