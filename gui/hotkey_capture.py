# -*- coding: utf-8 -*-
"""Widget to capture a hotkey by pressing keys (not typing names)."""

import tkinter as tk
from tkinter import ttk

from utils.hotkey_codec import format_hotkey_display, hotkey_from_tk_event, normalize_hotkey_spec


class HotkeyCapture(ttk.Frame):
    """Read-only field + button; captures key combination on the parent toplevel."""

    def __init__(self, parent, initial_value="", on_change=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._value = initial_value or ""
        self._on_change = on_change
        self._capturing = False
        self._bind_parent = None
        self._press_bind = None
        self._release_bind = None

        self.var = tk.StringVar(value=format_hotkey_display(self._value))
        self.entry = ttk.Entry(self, textvariable=self.var, state="readonly", width=34)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.btn = ttk.Button(self, text="Изменить…", width=10, command=self._start_capture)
        self.btn.pack(side=tk.LEFT, padx=(6, 0))

    def get_value(self) -> str:
        return self._value

    def set_value(self, spec: str) -> None:
        self._value = spec or ""
        self.var.set(format_hotkey_display(self._value))

    def _start_capture(self):
        if self._capturing:
            return
        self._capturing = True
        self.var.set("Нажмите сочетание…")
        self.btn.config(text="Отмена")

        top = self.winfo_toplevel()
        self._bind_parent = top
        self._press_bind = top.bind("<KeyPress>", self._on_key_press, add=True)
        self._release_bind = top.bind("<KeyRelease>", self._on_key_release, add=True)
        top.focus_force()

    def _stop_capture(self):
        if not self._capturing:
            return
        self._capturing = False
        self.btn.config(text="Изменить…")
        if self._bind_parent:
            if self._press_bind:
                self._bind_parent.unbind("<KeyPress>", self._press_bind)
            if self._release_bind:
                self._bind_parent.unbind("<KeyRelease>", self._release_bind)
        self._bind_parent = None
        self._press_bind = None
        self._release_bind = None
        self.var.set(format_hotkey_display(self._value))

    def _on_key_press(self, event):
        if not self._capturing:
            return
        if event.keysym == "Escape":
            self._stop_capture()
            return "break"

    def _on_key_release(self, event):
        if not self._capturing:
            return
        spec = hotkey_from_tk_event(event)
        if not spec:
            return "break"
        try:
            spec = normalize_hotkey_spec(spec)
        except ValueError:
            return "break"
        self._value = spec
        self._stop_capture()
        self.var.set(format_hotkey_display(spec))
        if self._on_change:
            self._on_change(spec)
        return "break"
