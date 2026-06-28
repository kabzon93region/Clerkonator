# -*- coding: utf-8 -*-
"""Dark theme for Tkinter / ttk widgets."""

import sys
import tkinter as tk
from tkinter import ttk

COLORS = {
    "bg": "#1a1a1d",
    "surface": "#252528",
    "surface2": "#2f2f33",
    "fg": "#e8e8ea",
    "fg_muted": "#9a9aa3",
    "accent": "#4a9eff",
    "accent_hover": "#6bb0ff",
    "border": "#3a3a40",
    "success": "#5cb85c",
    "warning": "#f0ad4e",
    "error": "#e74c3c",
    "text_bg": "#1f1f23",
    "select_bg": "#3d5a80",
    "select_fg": "#ffffff",
    "trough": "#2a2a2e",
}

# Windows: Segoe UI renders Cyrillic; Tk default often breaks in Combobox lists
UI_FONT = ("Segoe UI", 9)
UI_FONT_BOLD = ("Segoe UI", 11, "bold")


def _configure_cyrillic_fonts(root: tk.Tk, style: ttk.Style) -> None:
    """Ensure Tk/ttk widgets can display Cyrillic on Windows."""
    root.option_add("*Font", UI_FONT)
    root.option_add("*TCombobox*Listbox.font", UI_FONT)
    root.option_add("*TCombobox*Listbox.foreground", COLORS["fg"])
    root.option_add("*TCombobox*Listbox.background", COLORS["surface"])

    for widget_style in (
        "TLabel",
        "Muted.TLabel",
        "Header.TLabel",
        "Status.TLabel",
        "TButton",
        "Accent.TButton",
        "TEntry",
        "TCombobox",
        "TCheckbutton",
        "TRadiobutton",
        "TSpinbox",
        "TLabelframe",
        "TLabelframe.Label",
        "Vertical.TScrollbar",
    ):
        if widget_style == "Header.TLabel":
            style.configure(widget_style, font=UI_FONT_BOLD)
        else:
            style.configure(widget_style, font=UI_FONT)

    if sys.platform == "win32":
        try:
            # Tcl internal encoding for strings passed to native widgets
            root.tk.call("encoding", "system", "utf-8")
        except tk.TclError:
            pass


def apply_dark_theme(root: tk.Tk) -> dict:
    """Apply dark theme to root window and return color palette."""
    colors = COLORS.copy()
    root.configure(bg=colors["bg"])

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", background=colors["bg"], foreground=colors["fg"], bordercolor=colors["border"])
    style.configure("TFrame", background=colors["bg"])
    style.configure("TLabel", background=colors["bg"], foreground=colors["fg"])
    style.configure("Muted.TLabel", background=colors["bg"], foreground=colors["fg_muted"])
    style.configure("Header.TLabel", background=colors["bg"], foreground=colors["fg"], font=("Segoe UI", 11, "bold"))
    style.configure("Status.TLabel", background=colors["surface"], foreground=colors["fg"], padding=(6, 4))
    style.configure("TButton", background=colors["surface2"], foreground=colors["fg"], padding=(8, 4), borderwidth=1)
    style.map(
        "TButton",
        background=[("active", colors["accent"]), ("disabled", colors["surface"])],
        foreground=[("active", "#ffffff"), ("disabled", colors["fg_muted"])],
    )
    style.configure("Accent.TButton", background=colors["accent"], foreground="#ffffff")
    style.map(
        "Accent.TButton",
        background=[("active", colors["accent_hover"]), ("disabled", colors["surface2"])],
        foreground=[("disabled", colors["fg_muted"])],
    )
    style.configure("TProgressbar", background=colors["accent"], troughcolor=colors["trough"], borderwidth=0, thickness=8)
    style.configure("TLabelframe", background=colors["bg"], foreground=colors["fg_muted"])
    style.configure("TLabelframe.Label", background=colors["bg"], foreground=colors["fg_muted"])
    style.configure(
        "TEntry",
        fieldbackground=colors["text_bg"],
        foreground=colors["fg"],
        insertcolor=colors["fg"],
        bordercolor=colors["border"],
        lightcolor=colors["border"],
        darkcolor=colors["border"],
    )
    style.map(
        "TEntry",
        fieldbackground=[("readonly", colors["surface"]), ("disabled", colors["surface"])],
        foreground=[("disabled", colors["fg_muted"])],
    )
    style.configure(
        "TCombobox",
        fieldbackground=colors["text_bg"],
        background=colors["surface2"],
        foreground=colors["fg"],
        arrowcolor=colors["fg"],
        bordercolor=colors["border"],
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", colors["text_bg"]), ("disabled", colors["surface"])],
        foreground=[("disabled", colors["fg_muted"])],
        arrowcolor=[("disabled", colors["fg_muted"])],
    )
    style.configure("TCheckbutton", background=colors["bg"], foreground=colors["fg"])
    style.map(
        "TCheckbutton",
        background=[("active", colors["bg"])],
        foreground=[("active", colors["fg"])],
    )
    style.configure(
        "TRadiobutton",
        background=colors["bg"],
        foreground=colors["fg"],
        indicatorcolor=colors["text_bg"],
        bordercolor=colors["border"],
    )
    style.map(
        "TRadiobutton",
        background=[("active", colors["bg"])],
        foreground=[("active", colors["accent"])],
        indicatorcolor=[("selected", colors["accent"]), ("active", colors["accent_hover"])],
    )
    style.configure(
        "TSpinbox",
        fieldbackground=colors["text_bg"],
        foreground=colors["fg"],
        background=colors["surface2"],
        arrowcolor=colors["fg"],
        bordercolor=colors["border"],
        insertcolor=colors["fg"],
    )
    style.map(
        "TSpinbox",
        fieldbackground=[("readonly", colors["text_bg"]), ("disabled", colors["surface"])],
        foreground=[("disabled", colors["fg_muted"])],
        arrowcolor=[("disabled", colors["fg_muted"])],
    )
    style.configure(
        "Vertical.TScrollbar",
        background=colors["surface2"],
        troughcolor=colors["trough"],
        arrowcolor=colors["fg"],
        bordercolor=colors["border"],
    )
    style.configure(
        "Horizontal.TScrollbar",
        background=colors["surface2"],
        troughcolor=colors["trough"],
        arrowcolor=colors["fg"],
        bordercolor=colors["border"],
    )
    style.configure("TSeparator", background=colors["border"])

    _configure_cyrillic_fonts(root, style)

    root.option_add("*TCombobox*Listbox.background", colors["surface"])
    root.option_add("*TCombobox*Listbox.foreground", colors["fg"])
    root.option_add("*TCombobox*Listbox.selectBackground", colors["select_bg"])
    root.option_add("*TCombobox*Listbox.selectForeground", colors["select_fg"])

    # Fallback for native tk widgets (Spinbox/Entry internals on some Windows builds)
    root.option_add("*Entry.Background", colors["text_bg"])
    root.option_add("*Entry.Foreground", colors["fg"])
    root.option_add("*Entry.insertBackground", colors["fg"])
    root.option_add("*Listbox*Background", colors["text_bg"])
    root.option_add("*Listbox*Foreground", colors["fg"])

    return colors


def style_listbox(listbox: tk.Listbox, colors: dict) -> None:
    """Style a tk.Listbox for dark theme."""
    listbox.configure(
        bg=colors["text_bg"],
        fg=colors["fg"],
        selectbackground=colors["select_bg"],
        selectforeground=colors["select_fg"],
        highlightthickness=1,
        highlightbackground=colors["border"],
        highlightcolor=colors["accent"],
        activestyle="none",
        font=UI_FONT,
    )


def style_text_widget(text_widget: tk.Text, colors: dict) -> None:
    """Style a tk.Text widget for dark theme."""
    text_widget.configure(
        bg=colors["text_bg"],
        fg=colors["fg"],
        insertbackground=colors["fg"],
        selectbackground=colors["select_bg"],
        selectforeground=colors["select_fg"],
        relief="flat",
        highlightthickness=1,
        highlightbackground=colors["border"],
        highlightcolor=colors["accent"],
        padx=6,
        pady=4,
        font=UI_FONT,
    )
