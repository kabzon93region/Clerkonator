# -*- coding: utf-8 -*-
"""
System tray manager for the Clerkonator STT server.

Provides a tray icon with:
- Dynamic status tooltip (model name, engine, queue state)
- Context menu for model switching, reload, and shutdown
- Console show/hide toggle (--silent mode)

Status indicators
----------------
The tray icon shows a colored status dot:
- Green → ready (model loaded, idle)
- Yellow → loading model
- Blue → processing transcription
- Blinking red-white → error (2.5 Hz)

The icon antenna color also changes based on status.
"""

import ctypes
import os
import threading

from pystray import Icon, Menu, MenuItem

from utils.app_icon import get_server_tray_image
from utils.session_logger import get_logger

log = get_logger()

# Win32 constants for console window visibility
SW_HIDE = 0
SW_SHOW = 5


def _get_console_hwnd():
    """Get handle to the console window (Windows only)."""
    try:
        return ctypes.windll.kernel32.GetConsoleWindow()
    except Exception:
        return None


def show_console():
    """Show the console window."""
    hwnd = _get_console_hwnd()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, SW_SHOW)


def hide_console():
    """Hide the console window."""
    hwnd = _get_console_hwnd()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, SW_HIDE)


def toggle_console():
    """Toggle console window visibility."""
    hwnd = _get_console_hwnd()
    if not hwnd:
        return
    if ctypes.windll.user32.IsWindowVisible(hwnd):
        hide_console()
    else:
        show_console()


class ServerTrayManager:
    """System tray icon manager for the STT server.

    Updates the tooltip and icon periodically based on server state.
    Supports model switching via a submenu built from the model catalog.
    """

    def __init__(self, state, config, on_switch_model=None, on_reload=None, on_shutdown=None):
        self.state = state
        self.config = config
        self._cb_switch_model = on_switch_model
        self._cb_reload = on_reload
        self._cb_shutdown = on_shutdown

        self.icon = None
        self._lock = threading.Lock()
        self._thread = None
        self._ready = threading.Event()
        self._tray_image = get_server_tray_image("loading")
        self._console_visible = True
        self._model_map = {}  # combo_label -> model_id
        self._blink_active = False
        self._blink_thread = None
        self._blink_color_index = 0

    def _tooltip(self):
        """Dynamic tooltip based on server state."""
        state = self.state
        if not state:
            return "Clerkonator Server"
        if state.model_loading:
            model = state.model_name or ""
            return f"Clerkonator Server - Загрузка {model}..." if model else "Clerkonator Server - Загрузка модели..."
        if state.model_error:
            return f"Clerkonator Server - Ошибка: {state.model_error}"
        if state.model_loaded:
            q = state.queue_waiting + state.queue_active
            label = f"{state.model_name} ({state.engine}/{state.device})" if state.model_name else f"{state.engine}/{state.device}"
            if q > 0:
                return f"Clerkonator Server - {label} (очередь: {q})"
            return f"Clerkonator Server - {label} (готов)"
        return "Clerkonator Server - Ожидание"

    def _on_toggle_console(self, icon, item):
        toggle_console()
        self._console_visible = not self._console_visible

    def _on_show_status(self, icon, item):
        """Log current status to console."""
        state = self.state
        if not state:
            log.info("Status: unknown")
            return
        payload = state.health_payload()
        log.info(f"=== Server Status ===")
        for k, v in payload.items():
            log.info(f"  {k}: {v}")
        log.info(f"====================")

    def _on_switch_model_menu(self, icon, item):
        """Handle model selection from submenu."""
        label = item.text
        model_id = self._model_map.get(label, label)
        if self._cb_switch_model:
            log.info(f"Switching model to: {model_id}")
            threading.Thread(
                target=self._cb_switch_model, args=(model_id,), daemon=True
            ).start()

    def _build_model_submenu(self):
        """Build submenu with available models."""
        try:
            from utils.stt_model_catalog import list_local_stt_models
            models = list_local_stt_models()
            self._model_map = {}
            items = []
            for m in models:
                self._model_map[m.combo_label] = m.model_id
                items.append(MenuItem(m.combo_label, self._on_switch_model_menu))
            if not items:
                items.append(MenuItem("(нет моделей)", None, enabled=False))
            return Menu(*items)
        except Exception as e:
            log.warning(f"Could not list models: {e}")
            return Menu(MenuItem("(ошибка)", None, enabled=False))

    def _do_reload(self, icon, item):
        if self._cb_reload:
            log.info("Reload requested from tray")
            threading.Thread(target=self._cb_reload, daemon=True).start()

    def _do_shutdown(self, icon, item):
        if self._cb_shutdown:
            log.info("Shutdown requested from tray")
            self._cb_shutdown()

    def _build_menu(self):
        return Menu(
            MenuItem("Показать/Скрыть консоль", self._on_toggle_console, default=True),
            MenuItem("Статус", self._on_show_status),
            Menu.SEPARATOR,
            MenuItem("Модели", self._build_model_submenu()),
            MenuItem("Перезапустить сервер", self._do_reload),
            Menu.SEPARATOR,
            MenuItem("Выход", self._do_shutdown),
        )

    def _on_setup(self, icon):
        """Called when tray icon is created."""
        try:
            from pystray._util import win32

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
        log.info("Server tray icon visible")

    def start_in_thread(self):
        """Start tray icon in a dedicated background thread."""

        def tray_worker():
            try:
                menu = self._build_menu()
                icon = Icon(
                    f"STTServer_{os.getpid()}",
                    self._tray_image,
                    self._tooltip(),
                    menu,
                )
                with self._lock:
                    self.icon = icon
                log.info("Server tray thread running")
                icon.run(setup=self._on_setup)
            except Exception as e:
                log.error(f"Server tray error: {e}")
                import traceback
                log.error(traceback.format_exc())
            finally:
                with self._lock:
                    self.icon = None
                self._ready.set()
                log.info("Server tray thread stopped")

        self._thread = threading.Thread(target=tray_worker, daemon=True, name="ServerTray")
        self._thread.start()

        if not self._ready.wait(timeout=10):
            log.warning("Server tray did not become ready within 10 seconds")

        log.info("Server tray started")

    def _get_icon_status(self) -> str:
        """Map current server state to icon status key."""
        state = self.state
        if not state:
            return "default"
        if state.model_error:
            return "error"
        if state.model_loading:
            return "loading"
        if state.model_loaded:
            if state.queue_active > 0:
                return "processing"
            return "ready"
        return "default"

    def update_tooltip(self):
        """Update tray tooltip and icon (call periodically or on state change)."""
        with self._lock:
            icon = self.icon
        if icon:
            try:
                icon.title = self._tooltip()
                new_status = self._get_icon_status()
                # Handle error blinking
                if new_status == "error":
                    if not self._blink_active:
                        self._start_error_blink()
                else:
                    if self._blink_active:
                        self._stop_error_blink()
                    icon.icon = get_server_tray_image(new_status)
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
                    icon.icon = get_server_tray_image("error", dot_color=color)
                    self._blink_color_index += 1
                except Exception:
                    pass
            time.sleep(0.2)  # ~2.5 Hz toggle

    def update_model_menu(self):
        """Rebuild entire tray menu so model submenu is refreshed."""
        with self._lock:
            icon = self.icon
        if not icon:
            return
        try:
            icon.menu = self._build_menu()
            icon.update_menu()
            log.debug("Tray menu rebuilt with current models")
        except Exception as e:
            log.warning(f"update_model_menu error: {e}")

    def stop(self):
        """Stop tray icon."""
        with self._lock:
            icon = self.icon
        if icon:
            try:
                icon.stop()
            except Exception as e:
                log.error(f"Server tray stop error: {e}")
