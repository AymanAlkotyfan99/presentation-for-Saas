from __future__ import annotations

from collections.abc import Iterable


def infer_presentation_language(
    texts: Iterable[str],
    fallback: str | None = None,
) -> str:
    joined = " ".join(text or "" for text in texts)
    arabic = sum(1 for char in joined if "\u0600" <= char <= "\u06ff")
    cjk = sum(1 for char in joined if "\u3400" <= char <= "\u9fff")
    cyrillic = sum(1 for char in joined if "\u0400" <= char <= "\u052f")
    latin = sum(1 for char in joined if char.isascii() and char.isalpha())
    if arabic > max(cjk, cyrillic, latin * 0.2):
        return "Arabic"
    if cjk > max(arabic, cyrillic, latin * 0.2):
        return "Chinese"
    if cyrillic > max(arabic, cjk, latin * 0.2):
        return "Russian"
    if latin:
        return "English"
    return (fallback or "").strip()
