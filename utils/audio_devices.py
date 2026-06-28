# -*- coding: utf-8 -*-
"""Helpers for listing PyAudio input devices."""

from typing import List, Tuple, Optional

import pyaudio


def normalize_device_name(name) -> str:
    """
    Normalize audio device name for display.

    PyAudio/PortAudio on Windows may return names with wrong encoding
    (cp1251 bytes interpreted as latin-1, or UTF-8 as cp1251).
    """
    if name is None:
        return "Unknown device"

    if isinstance(name, bytes):
        for encoding in ("utf-8", "cp1251", "cp866"):
            try:
                return name.decode(encoding)
            except UnicodeDecodeError:
                continue
        return name.decode("utf-8", errors="replace")

    text = str(name).strip()
    if not text:
        return "Unknown device"

    # UTF-8 bytes misread as cp1251: "РњРёРє..." -> "Мик..."
    if any(ch in text for ch in ("Р", "С", "Ð", "Ñ")):
        try:
            repaired = text.encode("cp1251").decode("utf-8")
            if repaired:
                return repaired
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass

    # cp1251 bytes misread as latin-1
    try:
        repaired = text.encode("latin-1").decode("cp1251")
        if repaired:
            return repaired
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass

    return text


def list_input_devices() -> List[Tuple[int, str]]:
    """
    Return list of (device_index, display_name) for input devices.

    Index -1 means system default input.
    """
    devices: List[Tuple[int, str]] = [(-1, "По умолчанию (системный микрофон)")]
    audio = None
    try:
        audio = pyaudio.PyAudio()
        for i in range(audio.get_device_count()):
            try:
                info = audio.get_device_info_by_index(i)
                if int(info.get("maxInputChannels", 0)) > 0:
                    name = normalize_device_name(info.get("name", f"Device {i}"))
                    devices.append((i, f"{name} [#{i}]"))
            except Exception:
                continue
    finally:
        if audio is not None:
            audio.terminate()
    return devices


def resolve_device_index(configured_index: Optional[int]) -> Optional[int]:
    """Return PyAudio input device index or None for default."""
    if configured_index is None or configured_index < 0:
        return None
    return configured_index


def device_label_for_index(device_index: int) -> str:
    """Human-readable label for a device index."""
    for idx, label in list_input_devices():
        if idx == device_index:
            return label
    return f"Устройство #{device_index}"
