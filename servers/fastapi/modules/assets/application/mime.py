"""Bounded content sniffing; extensions are never authoritative."""

from __future__ import annotations

import io
import zipfile


ALLOWED_MIME_TYPES = frozenset(
    {
        "image/png", "image/jpeg", "image/gif", "image/webp", "image/tiff", "image/bmp",
        "application/pdf", "text/plain",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
)

_DECLARED_ALIASES = {
    "image/jpg": "image/jpeg",
    "application/x-pdf": "application/pdf",
}


def normalize_declared_mime(value: str) -> str:
    normalized = (value or "").split(";", 1)[0].strip().lower()
    return _DECLARED_ALIASES.get(normalized, normalized)


def detect_mime(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return "image/tiff"
    if data.startswith(b"BM"):
        return "image/bmp"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = set(archive.namelist())
                if "ppt/presentation.xml" in names:
                    return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                if "word/document.xml" in names:
                    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                if "xl/workbook.xml" in names:
                    return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        except (OSError, ValueError, zipfile.BadZipFile):
            pass
        return "application/zip"
    try:
        decoded = data[:1024 * 1024].decode("utf-8")
    except UnicodeDecodeError:
        return "application/octet-stream"
    if "\x00" not in decoded and sum(ord(char) < 9 or 13 < ord(char) < 32 for char in decoded) < 8:
        return "text/plain"
    return "application/octet-stream"


def validate_mime(*, declared: str, detected: str) -> None:
    declared = normalize_declared_mime(declared)
    if detected not in ALLOWED_MIME_TYPES:
        raise ValueError("Detected asset type is not allowed")
    if declared not in ALLOWED_MIME_TYPES:
        raise ValueError("Declared asset type is not allowed")
    if declared != detected:
        raise ValueError("Declared and detected asset types do not match")
