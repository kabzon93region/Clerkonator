# -*- coding: utf-8 -*-
"""Application icon generation and management for Clerkonator.

Generates tray icons (64x64 PIL images) and .ico files for:
- **Client** — microphone icon with status dot overlay
- **Server** — antenna/broadcast icon with status dot overlay

Status dot colors
-----------------
Client:
- None (transparent) → idle
- Red (220,50,50) → recording / error
- Yellow (230,180,0) → paused
- Blue (74,158,255) → processing
- Green (0,200,100) → connected

Server:
- Green → ready
- Yellow → loading
- Red → error
- Blue → processing

The ``dot_color`` parameter overrides the status color for blinking.
"""

import os
from pathlib import Path

from PIL import Image

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = _PROJECT_ROOT / "assets"
PNG_PATH = ASSETS_DIR / "app_icon.png"
ICO_PATH = ASSETS_DIR / "app_icon.ico"
SERVER_ICO_PATH = ASSETS_DIR / "server_icon.ico"


def ensure_icon_files() -> Path:
    """Ensure the client PNG and ICO files exist.

    If the PNG is missing, generates a fallback icon.
    If the ICO is missing or outdated, regenerates it from the PNG.
    Returns the path to the ICO file.
    """
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    if not PNG_PATH.exists():
        _create_fallback_png()

    if not ICO_PATH.exists() or ICO_PATH.stat().st_mtime < PNG_PATH.stat().st_mtime:
        img = Image.open(PNG_PATH).convert("RGBA")
        sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        img.save(ICO_PATH, format="ICO", sizes=sizes)

    return ICO_PATH


def get_tray_image() -> Image.Image:
    """Return a 64x64 in-memory copy for the system tray."""
    ensure_icon_files()
    with Image.open(PNG_PATH) as img:
        rgba = img.convert("RGBA")
        rgba.load()
        return rgba.resize((64, 64), Image.Resampling.LANCZOS)


def _add_status_dot(base_img: Image.Image, status_rgb) -> Image.Image:
    """Overlay a colored status dot on the bottom-right of an icon image.

    Args:
        base_img: The base icon image (RGBA, any size).
        status_rgb: RGB tuple (e.g. (220, 50, 50) for red).

    Returns a new image with the dot overlaid.
    """
    from PIL import ImageDraw
    img = base_img.copy()
    draw = ImageDraw.Draw(img)
    size = img.size[0]
    # Scale dot relative to image size
    dr = max(4, size // 6)
    dot_cx, dot_cy = size - dr - 2, size - dr - 2
    draw.ellipse(
        (dot_cx - dr, dot_cy - dr, dot_cx + dr, dot_cy + dr),
        fill=status_rgb + (255,), outline=(26, 26, 29, 255), width=max(1, dr // 4),
    )
    return img


_CLIENT_STATUS_DOT = {
    "idle":        None,
    "recording":   (220, 50, 50),
    "paused":      (230, 180, 0),
    "processing":  (74, 158, 255),
    "connected":   (0, 200, 100),
    "error":       (220, 50, 50),
}


def get_client_tray_image(status: str = "idle", dot_color=None) -> Image.Image:
    """Return 64x64 client tray icon with optional status dot.

    *status*: ``"idle"`` | ``"recording"`` | ``"paused"`` | ``"processing"`` | ``"connected"`` | ``"error"``
    *dot_color*: override the dot color (RGB tuple) for blinking
    """
    ensure_icon_files()
    with Image.open(PNG_PATH) as img:
        rgba = img.convert("RGBA")
        rgba.load()
        base = rgba.resize((64, 64), Image.Resampling.LANCZOS)
    dot_rgb = dot_color if dot_color is not None else _CLIENT_STATUS_DOT.get(status)
    if dot_rgb:
        return _add_status_dot(base, dot_rgb)
    return base


def get_icon_png() -> Image.Image:
    """Load full-size icon as PIL Image."""
    ensure_icon_files()
    with Image.open(PNG_PATH) as img:
        rgba = img.convert("RGBA")
        rgba.load()
        return rgba.copy()


def get_icon_ico_path() -> str:
    """Return path to .ico for Tk iconbitmap."""
    return str(ensure_icon_files())


def ensure_server_icon_files() -> Path:
    """Ensure server .ico exists; generate from server icon image."""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    # Always regenerate to keep in sync with icon changes
    img = _create_server_icon_image((100, 160, 220), None)  # default blue accent
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(SERVER_ICO_PATH, format="ICO", sizes=sizes)
    return SERVER_ICO_PATH


def get_server_icon_ico_path() -> str:
    """Return path to server .ico for PyInstaller."""
    return str(ensure_server_icon_files())


# ── Server tray icons ──────────────────────────────────────────────

def _create_server_icon_image(
    accent_rgb=(0, 200, 100),
    status_rgb=None,
) -> Image.Image:
    """Generate a server broadcast icon (256x256).

    *accent_rgb* – main antenna colour.
    *status_rgb*  – small status dot in bottom-right (None = no dot).
    """
    from PIL import ImageDraw

    size = 256
    img = Image.new("RGBA", (size, size), (26, 26, 29, 255))
    draw = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2

    # Antenna mast
    mast_top = cy - 45
    mast_bottom = cy + 30
    draw.rectangle((cx - 6, mast_top, cx + 6, mast_bottom), fill=accent_rgb + (255,))

    # Base triangle
    draw.polygon(
        [(cx - 30, mast_bottom + 35), (cx, mast_bottom - 5), (cx + 30, mast_bottom + 35)],
        fill=accent_rgb + (255,),
    )

    # Broadcast arcs (3 per side)
    for i, r in enumerate((28, 48, 68)):
        w = 7 - i * 2
        # Left
        draw.arc(
            (cx - r - 18, mast_top - r + 15, cx - r + 18, mast_top + r + 15),
            210, 330, fill=accent_rgb + (255,), width=w,
        )
        # Right
        draw.arc(
            (cx + r - 18, mast_top - r + 15, cx + r + 18, mast_top + r + 15),
            210, 330, fill=accent_rgb + (255,), width=w,
        )

    # Status dot
    if status_rgb:
        dr = 30
        dot_cx, dot_cy = size - 48, size - 48
        draw.ellipse(
            (dot_cx - dr, dot_cy - dr, dot_cx + dr, dot_cy + dr),
            fill=status_rgb + (255,), outline=(26, 26, 29, 255), width=6,
        )

    return img


def _server_icon_to_tray(img: Image.Image) -> Image.Image:
    return img.resize((64, 64), Image.Resampling.LANCZOS)


def get_server_tray_image(status: str = "default", dot_color=None) -> Image.Image:
    """Return 64x64 server tray icon.

    *status*: ``"ready"`` | ``"loading"`` | ``"error"`` | ``"processing"`` | ``"default"``
    *dot_color*: override the dot color (RGB tuple) for blinking
    """
    _STATUS = {
        "ready":      ((0, 200, 100),  (0, 255, 100)),
        "loading":    ((230, 180, 0),  (255, 220, 50)),
        "error":      ((220, 50, 50),  (255, 80, 80)),
        "processing": ((74, 158, 255), (120, 190, 255)),
    }
    accent, dot = _STATUS.get(status, ((100, 160, 220), None))
    if dot_color is not None:
        dot = dot_color
    return _server_icon_to_tray(_create_server_icon_image(accent, dot))


def _create_fallback_png() -> None:
    """Create a simple programmatic icon if PNG is missing."""
    from PIL import ImageDraw

    size = 256
    img = Image.new("RGBA", (size, size), (26, 26, 29, 255))
    draw = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2 + 10
    draw.ellipse((cx - 28, cy - 55, cx + 28, cy + 5), fill=(74, 158, 255, 255))
    draw.rectangle((cx - 10, cy + 5, cx + 10, cy + 45), fill=(74, 158, 255, 255))
    draw.ellipse((cx - 35, cy + 40, cx + 35, cy + 58), fill=(74, 158, 255, 255))
    for i, offset in enumerate((55, 75, 95)):
        draw.arc((cx + offset - 20, cy - 30, cx + offset + 20, cy + 30), -60, 60, fill=(120, 190, 255, 255), width=6 - i)
    img.save(PNG_PATH, format="PNG")
