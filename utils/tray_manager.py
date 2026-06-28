#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
System tray manager for the Clerkonator client.

Provides a tray icon with a context menu for:
- Showing the main window
- Start / pause / cancel / finish recording
- Opening settings
- Quitting the application

Threading
---------
The tray icon runs in its own background thread (pystray requirement).
Tkinter must stay on the main thread on Windows.
Communication with the app happens via ``app.gui_queue``.

Status indicators
----------------
The tray icon shows a colored status dot:
- Red → recording
- Yellow → paused
- Blue → processing
- Green → connected / ready
- Blinking red-white → error (2.5 Hz)
"""

import os
import sys
import threading

from pystray import Icon, Menu, MenuItem

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from utils.app_icon import get_client_tray_image
from utils.session_logger import get_logger

log = get_logger()


class TrayManager:
    """System tray icon manager for the client application.

    Manages the tray icon image, tooltip, context menu, and status updates.
    Delegates user actions to the app via ``gui_queue``.
    """

    def __init__(self, app):
        self.app = app
        self.is_running = False
        self.icon = None
        self.status = "Starting"
        self._tray_image = get_client_tray_image()
        self._ready = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self._blink_active = False
        self._blink_thread = None
        self._blink_color_index = 0

    def show_main_window(self, icon, item):
        try:
            self.app.show_gui()
        except Exception as e:
            log.error(f"Tray show window: {e}")

    def start_recording(self, icon, item):
        self.app.tray_start_recording()

    def toggle_pause(self, icon, item):
        if self.app.is_paused:
            self.app.tray_resume_recording()
        else:
            self.app.tray_pause_recording()

    def cancel_recording(self, icon, item):
        self.app.tray_cancel_recording()

    def finish_recording(self, icon, item):
        self.app.tray_finish_recording()

    def show_settings(self, icon, item):
        self.app.show_settings()

    def quit_application(self, icon, item):
        log.info("Quit from tray")
        self.is_running = False
        try:
            self.app.stop()
        except Exception as e:
            log.error(f"Quit error: {e}")

    def _tooltip(self):
        # ASCII tooltip — stable on all Windows tray implementations
        return f"Clerkonator - {self.status}"

    def update_status(self, status):
        """Update status and tray icon."""
        self.status = status
        # Map app status to icon status
        icon_status = self._map_status(status)
        with self._lock:
            icon = self.icon
        if icon:
            try:
                # Handle error blinking
                if icon_status == "error":
                    if not self._blink_active:
                        self._start_error_blink()
                else:
                    if self._blink_active:
                        self._stop_error_blink()
                    icon.icon = get_client_tray_image(icon_status)
            except Exception:
                pass

    def _start_error_blink(self):
        """Start blinking the error dot between red and white."""
        self._blink_active = True
        self._blink_color_index = 0
        self._blink_thread = threading.Thread(target=self._blink_loop, daemon=True)
        self._blink_thread.start()

    def _stop_error_blink(self):
        """Stop blinking."""
        self._blink_active = False

    def _blink_loop(self):
        """Blink loop: alternate dot color at ~2.5 Hz."""
        import time
        colors = [(220, 50, 50), (255, 255, 255)]  # red, white
        while self._blink_active:
            with self._lock:
                icon = self.icon
            if icon:
                try:
                    color = colors[self._blink_color_index % 2]
                    icon.icon = get_client_tray_image("error", dot_color=color)
                    self._blink_color_index += 1
                except Exception:
                    pass
            time.sleep(0.2)  # ~2.5 Hz toggle

    def _map_status(self, status: str) -> str:
        """Map app status string (Russian or English) to icon status key.

        Returns one of: "idle", "recording", "paused", "processing",
        "connected", "error".
        """
        s = status.lower()
        # Russian statuses
        if "запис" in s:  # запись, записи
            return "recording"
        if "пауз" in s:  # пауза
            return "paused"
        if "распознав" in s or "обработ" in s:  # распознавание, обработка
            return "processing"
        if "подключ" in s or "сервер" in s:  # подключено, подключение, сервер
            return "connected"
        if "ошиб" in s or "не подключ" in s:  # ошибка, не подключено
            return "error" if "ошиб" in s else "idle"
        if "готов" in s or "загрузк" in s:  # готово, загрузка модели
            return "processing" if "загрузк" in s else "idle"
        # English fallback
        if "record" in s and "pause" not in s:
            return "recording"
        if "pause" in s:
            return "paused"
        if "process" in s or "recogni" in s or "convert" in s:
            return "processing"
        if "connect" in s:
            return "connected"
        if "error" in s or "fail" in s:
            return "error"
        return "idle"

    def _build_menu(self):
        return Menu(
            MenuItem("Открыть интерфейс", self.show_main_window, default=True),
            Menu.SEPARATOR,
            MenuItem("Начать запись", self.start_recording),
            MenuItem("Пауза / Продолжить", self.toggle_pause),
            MenuItem("Отмена записи", self.cancel_recording),
            MenuItem("Завершить и распознать", self.finish_recording),
            Menu.SEPARATOR,
            MenuItem("Настройки бэкенда", self.show_settings),
            Menu.SEPARATOR,
            MenuItem("Выход", self.quit_application),
        )

    def _on_setup(self, icon):
        try:
            import ctypes
            from pystray._util import win32

            # Required on Windows 10/11 for stable tray icon and tooltip
            win32.Shell_NotifyIcon(
                win32.NIM_SETVERSION,
                win32.NOTIFYICONDATAW(
                    cbSize=ctypes.sizeof(win32.NOTIFYICONDATAW),
                    hWnd=icon._hwnd,
                    hID=id(icon),
                    uFlags=win32.NIF_INFO,
                    uVersion=4,
                ),
            )
        except Exception as e:
            log.warning(f"Tray NIM_SETVERSION: {e}")

        icon.visible = True
        self._ready.set()
        log.info("Tray icon visible")

    def start_in_thread(self):
        """Start tray icon in a dedicated background thread."""

        def tray_worker():
            try:
                menu = self._build_menu()
                icon = Icon(
                    f"Clerkonator_{os.getpid()}",
                    self._tray_image,
                    self._tooltip(),
                    menu,
                )
                with self._lock:
                    self.icon = icon
                self.is_running = True
                log.info("Tray manager thread running")
                icon.run(setup=self._on_setup)
            except Exception as e:
                log.error(f"Tray manager error: {e}")
                import traceback
                log.error(traceback.format_exc())
            finally:
                with self._lock:
                    self.icon = None
                self.is_running = False
                self._ready.set()
                log.info("Tray manager thread stopped")

        self._thread = threading.Thread(target=tray_worker, daemon=True, name="TrayManager")
        self._thread.start()

        if not self._ready.wait(timeout=10):
            log.warning("Tray icon did not become ready within 10 seconds")

        log.info("Tray manager started")

    def stop(self):
        self.is_running = False
        with self._lock:
            icon = self.icon
        if icon:
            try:
                icon.stop()
            except Exception as e:
                log.error(f"Tray stop error: {e}")
