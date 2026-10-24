"""Wallpaper-derived accent palette and Tk widget recoloring for AirLink.

The app samples the current Windows desktop wallpaper and derives a dark,
tinted UI palette from its dominant saturated hue. Tkinter does not provide a
native acrylic blur, so this changes app/panel colors rather than applying the
actual Windows Mica/Acrylic material effect.
"""
from __future__ import annotations

import colorsys
import ctypes
import os
from pathlib import Path
from typing import Any

DEFAULT_PALETTE = {
    "BG": "#0b1020",
    "PANEL": "#121a2e",
    "PANEL2": "#17223a",
    "PANEL3": "#13223a",
    "BORDER": "#263450",
    "BORDER_ACCENT": "#2a4770",
    "TEXT": "#edf3ff",
    "MUTED": "#9aa9c4",
    "BLUE": "#6aa8ff",
    "CYAN": "#61e6dc",
    "GREEN": "#69e0a3",
    "ORANGE": "#ffca78",
    "BUTTON_TEXT": "#07101f",
}

_COLOR_OPTIONS = (
    "background", "foreground", "activebackground", "activeforeground",
    "highlightbackground", "highlightcolor", "insertbackground",
    "selectbackground", "selectforeground",
)

# Legacy fixed colors already present in the prototype. Mapping them lets the
# first automatic wallpaper refresh recolor existing widgets without rebuilding
# the familiar dashboard.
_COLOR_TO_ROLE: dict[str, str] = {
    "#0b1020": "BG",
    "#121a2e": "PANEL",
    "#17223a": "PANEL2",
    "#13223a": "PANEL3",
    "#263450": "BORDER",
    "#2a4770": "BORDER_ACCENT",
    "#edf3ff": "TEXT",
    "#9aa9c4": "MUTED",
    "#6aa8ff": "BLUE",
    "#61e6dc": "CYAN",
    "#69e0a3": "GREEN",
    "#ffca78": "ORANGE",
    "#07101f": "BUTTON_TEXT",
    "#112b2a": "PANEL2",
    "#657693": "MUTED",
    "#203553": "PANEL2",
    "#314462": "BORDER",
    "#7485a3": "MUTED",
}


def current_wallpaper_path() -> str | None:
    """Return the active Windows desktop wallpaper path, if available."""
    if os.name != "nt":
        return None
    try:
        # SPI_GETDESKWALLPAPER works for the current desktop wallpaper path.
        buf = ctypes.create_unicode_buffer(32768)
        ok = ctypes.windll.user32.SystemParametersInfoW(0x0073, len(buf), buf, 0)
        if ok and buf.value and Path(buf.value).is_file():
            return buf.value
    except Exception:
        pass

    # Registry fallback for Windows versions where the SPI call is unavailable.
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop") as key:
            value, _ = winreg.QueryValueEx(key, "WallPaper")
        if value and Path(value).is_file():
            return value
    except Exception:
        pass
    return None


def palette_for_wallpaper(path: str | None = None) -> dict[str, str]:
    """Create a dark palette tinted with the wallpaper's dominant vivid hue."""
    try:
        from PIL import Image, ImageOps
        image_path = path or current_wallpaper_path()
        if not image_path or not Path(image_path).is_file():
            return dict(DEFAULT_PALETTE)
        with Image.open(image_path) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((64, 64))
            pixels = list(image.get_flattened_data())
    except Exception:
        return dict(DEFAULT_PALETTE)

    hue_scores = [0.0] * 24
    hue_pixels: list[list[tuple[float, float, float]]] = [[] for _ in range(24)]
    average_brightness = 0.0
    average_saturation = 0.0
    usable_count = 0
    for red, green, blue in pixels:
        h, s, v = colorsys.rgb_to_hsv(red / 255.0, green / 255.0, blue / 255.0)
        average_brightness += v
        average_saturation += s
        usable_count += 1
        if s >= 0.20 and 0.14 <= v <= 0.95:
            index = min(23, int(h * 24))
            hue_scores[index] += s * (0.65 + min(v, 0.8))
            hue_pixels[index].append((h, s, v))

    if not usable_count:
        return dict(DEFAULT_PALETTE)

    avg_v = average_brightness / usable_count
    avg_s = average_saturation / usable_count
    if max(hue_scores, default=0) > 0:
        dominant = max(range(24), key=lambda idx: hue_scores[idx])
        selected = hue_pixels[dominant]
        h = sum(p[0] for p in selected) / len(selected)
        wallpaper_sat = sum(p[1] for p in selected) / len(selected)
        theme_sat = max(0.46, min(0.82, wallpaper_sat))
        accent = _hsv_hex(h, theme_sat, 0.98)
        # A slightly offset, softer companion accent creates the glassy highlight.
        accent2 = _hsv_hex((h + 0.035) % 1.0, max(0.42, theme_sat * 0.76), 0.96)
        tint_sat = max(0.16, min(0.38, wallpaper_sat * 0.44))
    else:
        # Neutral/monochrome wallpapers get a subtle slate-blue theme instead of
        # an arbitrary bright hue.
        h = 0.59
        tint_sat = 0.11 if avg_s < 0.12 else 0.18
        accent = "#a7c9ee" if avg_v < 0.48 else "#4777a8"
        accent2 = "#8caed1" if avg_v < 0.48 else "#5c88b4"

    # Keep surfaces dark for legibility, but shift their hue with the wallpaper.
    palette = {
        "BG": _hsv_hex(h, tint_sat * 0.80, 0.055),
        "PANEL": _hsv_hex(h, tint_sat, 0.092),
        "PANEL2": _hsv_hex(h, min(0.48, tint_sat * 1.18), 0.135),
        "PANEL3": _hsv_hex(h, min(0.50, tint_sat * 1.25), 0.165),
        "BORDER": _hsv_hex(h, min(0.52, tint_sat * 1.25), 0.255),
        "BORDER_ACCENT": _hsv_hex(h, min(0.70, max(0.33, wallpaper_sat * 0.72)), 0.34),
        "TEXT": "#edf3ff",
        "MUTED": _hsv_hex(h, 0.18, 0.70),
        "BLUE": accent,
        "CYAN": accent2,
        "GREEN": "#69e0a3",
        "ORANGE": "#ffca78",
        "BUTTON_TEXT": "#07101f" if _relative_luminance(accent) > 0.43 else "#ffffff",
    }
    return palette


def _hsv_hex(h: float, s: float, v: float) -> str:
    r, g, b = colorsys.hsv_to_rgb(max(0.0, min(1.0, h)), max(0.0, min(1.0, s)), max(0.0, min(1.0, v)))
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


def _relative_luminance(hex_color: str) -> float:
    value = hex_color.lstrip("#")
    r, g, b = (int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def register_palette(palette: dict[str, str]) -> None:
    """Remember current palette values so newly created Tk widgets can adapt too."""
    for role, value in palette.items():
        _COLOR_TO_ROLE[value.lower()] = role


def recolor_widget_tree(root: Any, palette: dict[str, str]) -> None:
    """Recolor Tk widgets by their semantic color role, preserving status colors."""
    register_palette(palette)
    stack = [root]
    while stack:
        widget = stack.pop()
        try:
            children = widget.winfo_children()
        except Exception:
            children = []
        stack.extend(children)

        roles = getattr(widget, "_airlink_theme_color_roles", None)
        if roles is None:
            roles = {}
            for option in _COLOR_OPTIONS:
                try:
                    value = str(widget.cget(option)).lower()
                except Exception:
                    continue
                roles[option] = _COLOR_TO_ROLE.get(value)
            try:
                widget._airlink_theme_color_roles = roles
            except Exception:
                pass

        for option, role in roles.items():
            if role and role in palette:
                try:
                    widget.configure(**{option: palette[role]})
                except Exception:
                    pass
