# -*- coding: utf-8 -*-
"""Global system hotkeys via pynput (layout-independent).

Registers configurable global hotkeys that work even when the application
window is not focused. Uses pynput's ``GlobalHotKeys`` listener which
operates at the OS level (Windows hook).

Supported hotkeys (configured in ``config.client.json``):
- ``hotkeys.show_window``    — show/hide the GUI window
- ``hotkeys.record_toggle``   — start recording or finish and transcribe
- ``hotkeys.pause_recording`` — pause/resume recording
- ``hotkeys.cancel_recording`` — cancel current recording
"""

import threading

from pynput.keyboard import GlobalHotKeys

from utils.hotkey_codec import to_pynput_hotkey
from utils.session_logger import get_logger

log = get_logger()


class GlobalHotkeyService:
    """Background listener for configured global hotkeys.

    Reads hotkey specs from config on ``start()`` and ``reload()``.
    Maps each pynput hotkey string to a callback method.
    """

    def __init__(self, app):
        self.app = app
        self._listener = None
        self._lock = threading.Lock()

    def start(self):
        self.reload()

    def stop(self):
        with self._lock:
            if self._listener:
                try:
                    self._listener.stop()
                except Exception as exc:
                    log.warning(f"Hotkey stop error: {exc}")
                self._listener = None

    def reload(self):
        config = self.app.config
        mapping = {}

        # Show/hide window
        show_spec = config.get("hotkeys.show_window", "")
        if show_spec:
            try:
                pynput_key = to_pynput_hotkey(show_spec)
                mapping[pynput_key] = self._on_show_window
                log.debug(f"Registered show_window hotkey: {show_spec} -> {pynput_key}")
            except ValueError as exc:
                log.warning(f"Invalid show_window hotkey: {exc}")

        # Record toggle (start/finish)
        record_spec = config.get("hotkeys.record_toggle", "")
        if record_spec:
            try:
                pynput_key = to_pynput_hotkey(record_spec)
                mapping[pynput_key] = self._on_record_toggle
                log.debug(f"Registered record_toggle hotkey: {record_spec} -> {pynput_key}")
            except ValueError as exc:
                log.warning(f"Invalid record_toggle hotkey: {exc}")

        # Pause/resume recording
        pause_spec = config.get("hotkeys.pause_recording", "")
        if pause_spec:
            try:
                pynput_key = to_pynput_hotkey(pause_spec)
                mapping[pynput_key] = self._on_pause_toggle
                log.debug(f"Registered pause_recording hotkey: {pause_spec} -> {pynput_key}")
            except ValueError as exc:
                log.warning(f"Invalid pause_recording hotkey: {exc}")

        # Cancel recording
        cancel_spec = config.get("hotkeys.cancel_recording", "")
        if cancel_spec:
            try:
                pynput_key = to_pynput_hotkey(cancel_spec)
                mapping[pynput_key] = self._on_cancel_recording
                log.debug(f"Registered cancel_recording hotkey: {cancel_spec} -> {pynput_key}")
            except ValueError as exc:
                log.warning(f"Invalid cancel_recording hotkey: {exc}")

        with self._lock:
            if self._listener:
                try:
                    self._listener.stop()
                except Exception:
                    pass
                self._listener = None

            if not mapping:
                log.info("Global hotkeys disabled (none configured)")
                return

            try:
                self._listener = GlobalHotKeys(mapping)
                self._listener.start()
                log.info("Global hotkeys registered: " + ", ".join(mapping.keys()))
            except Exception as exc:
                log.error(f"Failed to start global hotkeys: {exc}")
                self._listener = None

    def _on_show_window(self):
        try:
            gui = self.app.gui_window
            if not gui:
                return

            def toggle():
                if gui.window.winfo_viewable():
                    gui.hide_window()
                else:
                    gui.show()

            gui.window.after(0, toggle)
        except Exception as exc:
            log.error(f"show_window hotkey error: {exc}")

    def _on_record_toggle(self):
        try:
            self.app.toggle_recording()
        except Exception as exc:
            log.error(f"record_toggle hotkey error: {exc}")

    def _on_pause_toggle(self):
        try:
            if self.app.is_recording:
                if self.app.is_paused:
                    self.app.gui_queue.put(("resume_recording", None))
                else:
                    self.app.gui_queue.put(("pause_recording", None))
        except Exception as exc:
            log.error(f"pause_recording hotkey error: {exc}")

    def _on_cancel_recording(self):
        try:
            if self.app.is_recording:
                self.app.gui_queue.put(("cancel_recording", None))
        except Exception as exc:
            log.error(f"cancel_recording hotkey error: {exc}")
