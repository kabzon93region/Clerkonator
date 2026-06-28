# -*- coding: utf-8 -*-
"""Layout-independent Ctrl shortcuts for Tk widgets (RU/EN keyboard)."""

import tkinter as tk

# Windows virtual-key codes (physical keys)
KC_A = 65
KC_C = 67
KC_V = 86
KC_X = 88
KC_Z = 90


def bind_text_shortcuts(widget: tk.Widget) -> None:
    """Copy/Cut/Paste/Select all — works with Russian keyboard layout."""
    widget.bind("<KeyPress>", _on_ctrl_shortcut, add=True)


def _on_ctrl_shortcut(event):
    if not (int(event.state) & 0x4):
        return

    widget = event.widget
    keycode = int(event.keycode)

    try:
        if keycode == KC_C:
            if hasattr(widget, "selection_present") and widget.selection_present():
                widget.event_generate("<<Copy>>")
                return "break"
        elif keycode == KC_X:
            if hasattr(widget, "selection_present") and widget.selection_present():
                widget.event_generate("<<Cut>>")
                return "break"
        elif keycode == KC_V:
            widget.event_generate("<<Paste>>")
            return "break"
        elif keycode == KC_A:
            widget.event_generate("<<SelectAll>>")
            return "break"
        elif keycode == KC_Z:
            widget.event_generate("<<Undo>>")
            return "break"
    except tk.TclError:
        pass
    return None
