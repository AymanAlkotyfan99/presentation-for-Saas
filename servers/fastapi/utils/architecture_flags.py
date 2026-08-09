"""Temporary migration flags for the V1-to-V2 strangler path.

Defaults preserve the current production behavior. Flags are deliberately
read at call time so operators can set them before process startup and tests
can exercise either branch without module reloading.
"""

import os
import uuid


def _enabled(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def architecture_facades_enabled() -> bool:
    return _enabled("ARCHITECTURE_FACADES_ENABLED", True)


def legacy_v1_reads_enabled() -> bool:
    return _enabled("LEGACY_V1_READS_ENABLED", True)


def legacy_v1_writes_enabled() -> bool:
    return _enabled("LEGACY_V1_WRITES_ENABLED", True)


def canonical_document_reads_enabled() -> bool:
    return _enabled("CANONICAL_DOCUMENT_READS_ENABLED", False)


def canonical_document_writes_enabled() -> bool:
    return _enabled("CANONICAL_DOCUMENT_WRITES_ENABLED", False)


def canonical_shadow_render_enabled() -> bool:
    return _enabled("CANONICAL_SHADOW_RENDER_ENABLED", False)


def legacy_document_fallback_enabled() -> bool:
    return _enabled("LEGACY_DOCUMENT_FALLBACK_ENABLED", True)


def canonical_internal_cohort_allows(
    presentation_id: uuid.UUID, owner_id: uuid.UUID | None
) -> bool:
    """Resolve the explicit operator-managed cohort without percentages or PII.

    Values are comma-separated `presentation:<uuid>` or `owner:<uuid>` tokens.
    A bare UUID is treated as a presentation ID for backwards-compatible ops
    ergonomics. Empty and malformed values fail closed.
    """

    entries = {
        entry.strip().lower()
        for entry in os.getenv("CANONICAL_INTERNAL_COHORT", "").split(",")
        if entry.strip()
    }
    presentation_tokens = {
        str(presentation_id).lower(), f"presentation:{presentation_id}".lower()
    }
    owner_tokens = {f"owner:{owner_id}".lower()} if owner_id else set()
    return bool(entries & (presentation_tokens | owner_tokens))


def require_legacy_v1_read(version: object) -> None:
    if getattr(version, "value", version) == "v1-standard" and not legacy_v1_reads_enabled():
        raise LegacyV1ReadDisabledError("Legacy V1 presentation reads are disabled")


def require_legacy_v1_write(version: object) -> None:
    if getattr(version, "value", version) == "v1-standard" and not legacy_v1_writes_enabled():
        raise LegacyV1WriteDisabledError("Legacy V1 presentation writes are disabled")


class LegacyV1ReadDisabledError(RuntimeError):
    pass


class LegacyV1WriteDisabledError(RuntimeError):
    pass
