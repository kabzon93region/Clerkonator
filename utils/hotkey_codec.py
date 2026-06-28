# -*- coding: utf-8 -*-
"""Hotkey string format and conversion for pynput / UI."""

from __future__ import annotations

from typing import List, Optional

# Windows virtual-key codes for Latin keys (layout-independent)
_KEYCODE_TO_NAME = {
    **{code: chr(code).lower() for code in range(ord("A"), ord("Z") + 1)},
    **{code: chr(code).lower() for code in range(ord("0"), ord("9") + 1)},
    186: ";",
    187: "=",
    188: ",",
    189: "-",
    190: ".",
    191: "/",
    192: "`",
    219: "[",
    220: "\\",
    221: "]",
    222: "'",
}

_SPECIAL_KEYSYMS = {
    "space": "space",
    "return": "enter",
    "tab": "tab",
    "escape": "escape",
    "backspace": "backspace",
    "delete": "delete",
    "insert": "insert",
    "home": "home",
    "end": "end",
    "prior": "page_up",
    "next": "page_down",
    "pause": "pause",
    **{f"f{i}": f"f{i}" for i in range(1, 25)},
}

_MODIFIER_ORDER = ("ctrl", "shift", "alt", "win")


def format_hotkey_display(spec: str) -> str:
    """ctrl+shift+r -> Ctrl + Shift + R"""
    if not spec:
        return "не задано"
    parts = []
    for token in spec.lower().split("+"):
        token = token.strip()
        if not token:
            continue
        if token in _MODIFIER_ORDER:
            parts.append(token.capitalize())
        elif token == "win":
            parts.append("Win")
        elif len(token) == 1:
            parts.append(token.upper())
        else:
            parts.append(token.replace("_", " ").title())
    return " + ".join(parts)


def normalize_hotkey_spec(spec: str) -> str:
    """Normalize and validate hotkey string."""
    if not spec or not str(spec).strip():
        raise ValueError("Пустое сочетание клавиш")

    tokens = [t.strip().lower() for t in str(spec).split("+") if t.strip()]
    if not tokens:
        raise ValueError("Пустое сочетание клавиш")

    mods = []
    main = None
    for token in tokens:
        if token in ("control", "ctrl", "ctrl_l", "ctrl_r"):
            if "ctrl" not in mods:
                mods.append("ctrl")
        elif token in ("shift", "shift_l", "shift_r"):
            if "shift" not in mods:
                mods.append("shift")
        elif token in ("alt", "alt_l", "alt_r", "alt_gr", "menu"):
            if "alt" not in mods:
                mods.append("alt")
        elif token in ("win", "cmd", "super", "windows"):
            if "win" not in mods:
                mods.append("win")
        else:
            if main is not None:
                raise ValueError("Укажите одну основную клавишу")
            main = token

    if main is None:
        raise ValueError("Нужна основная клавиша, не только модификаторы")

    ordered_mods = [m for m in _MODIFIER_ORDER if m in mods]
    return "+".join(ordered_mods + [main])


def to_pynput_hotkey(spec: str) -> str:
    """Convert config spec to pynput GlobalHotKeys format."""
    normalized = normalize_hotkey_spec(spec)
    parts = []
    for token in normalized.split("+"):
        if token == "ctrl":
            parts.append("<ctrl>")
        elif token == "shift":
            parts.append("<shift>")
        elif token == "alt":
            parts.append("<alt>")
        elif token == "win":
            parts.append("<cmd>")
        elif token in _SPECIAL_KEYSYMS.values() or token.startswith("f"):
            parts.append(f"<{token}>")
        elif len(token) == 1:
            parts.append(token)
        else:
            parts.append(token)
    return "+".join(parts)


def hotkey_from_tk_event(event) -> Optional[str]:
    """Build hotkey spec from Tk KeyRelease (layout-independent main key)."""
    mods: List[str] = []
    state = int(getattr(event, "state", 0))
    if state & 0x4:
        mods.append("ctrl")
    if state & 0x1:
        mods.append("shift")
    if state & 0x8 or state & 0x20000:
        mods.append("alt")
    if state & 0x40:
        mods.append("win")

    keysym = str(getattr(event, "keysym", "") or "").lower()
    if keysym in ("control_l", "control_r", "shift_l", "shift_r", "alt_l", "alt_r", "win_l", "win_r"):
        return None

    keycode = int(getattr(event, "keycode", 0) or 0)
    if keycode in _KEYCODE_TO_NAME:
        main = _KEYCODE_TO_NAME[keycode]
    elif keysym in _SPECIAL_KEYSYMS:
        main = _SPECIAL_KEYSYMS[keysym]
    else:
        return None

    ordered_mods = [m for m in _MODIFIER_ORDER if m in mods]
    if not ordered_mods and main not in _SPECIAL_KEYSYMS.values() and not main.startswith("f"):
        # Require at least one modifier for global shortcuts
        return None

    try:
        return normalize_hotkey_spec("+".join(ordered_mods + [main]))
    except ValueError:
        return None


def matches_hotkey_tk_event(event, spec: str) -> bool:
    """True if Tk key event matches configured hotkey."""
    if not spec:
        return False
    parsed = hotkey_from_tk_event(event)
    if not parsed:
        return False
    try:
        return parsed == normalize_hotkey_spec(spec)
    except ValueError:
        return False
