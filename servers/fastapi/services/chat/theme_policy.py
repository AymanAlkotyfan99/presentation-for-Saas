"""Pure theme selection policy extracted from the chat memory adapter."""

import re
from typing import Any


def sanitize_theme_id(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")[:64]


def normalize_hex_color(value: str) -> str | None:
    normalized = value.strip().lower().removeprefix("#")
    if len(normalized) == 3:
        normalized = "".join(ch * 2 for ch in normalized)
    return f"#{normalized}" if re.fullmatch(r"[0-9a-f]{6}", normalized) else None


def find_theme_by_id(themes: list[dict[str, Any]], theme_id: str) -> dict[str, Any] | None:
    normalized = theme_id.strip().lower()
    return next(
        (theme for theme in themes if str(theme.get("id") or "").strip().lower() == normalized),
        None,
    )


def extract_theme_name(theme: dict[str, Any] | None) -> str | None:
    if not isinstance(theme, dict):
        return None
    for key in ("name", "id"):
        value = theme.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def is_dark_hex(hex_color: str) -> bool:
    normalized = hex_color.strip().lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", normalized):
        return False
    red, green, blue = (int(normalized[index:index + 2], 16) for index in (0, 2, 4))
    return (0.299 * red + 0.587 * green + 0.114 * blue) / 255 < 0.5


def is_dark_theme(theme: dict[str, Any] | None) -> bool:
    data = theme.get("data") if isinstance(theme, dict) else None
    colors = data.get("colors") if isinstance(data, dict) else None
    background = colors.get("background") if isinstance(colors, dict) else None
    return isinstance(background, str) and is_dark_hex(background)


def select_theme_for_query(
    requested_theme: str,
    available_themes: list[dict[str, Any]],
    current_theme: dict[str, Any] | None,
) -> dict[str, Any] | None:
    query = requested_theme.strip().lower()
    if not query:
        return None
    for theme in available_themes:
        if query in {
            str(theme.get("id") or "").strip().lower(),
            str(theme.get("name") or "").strip().lower(),
        }:
            return theme
    tokens = [token for token in re.split(r"[\s_-]+", query) if token]
    preferred_ids: tuple[str, ...] = ()
    if "dark" in tokens or any(token in query for token in ("night", "black")):
        preferred_ids = ("professional-dark", "edge-yellow")
    elif "light" in tokens or any(token in query for token in ("bright", "white")):
        preferred_ids = ("professional-blue", "mint-blue", "light-rose")
    for theme_id in preferred_ids:
        if theme := find_theme_by_id(available_themes, theme_id):
            return theme
    current_id = str((current_theme or {}).get("id") or "").strip().lower()
    if any(token in query for token in ("another", "different", "change")):
        candidates = [theme for theme in available_themes if str(theme.get("id") or "").strip().lower() != current_id]
        opposite = not is_dark_theme(current_theme) if current_theme else True
        return next((theme for theme in candidates if is_dark_theme(theme) == opposite), candidates[0] if candidates else None)
    for theme in available_themes:
        haystack = " ".join(str(theme.get(key) or "").strip().lower() for key in ("id", "name", "description"))
        if query in haystack or (tokens and all(token in haystack for token in tokens)):
            return theme
    return None
