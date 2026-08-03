"""Temporary migration flags for the V1-to-V2 strangler path.

Defaults preserve the current production behavior. Flags are deliberately
read at call time so operators can set them before process startup and tests
can exercise either branch without module reloading.
"""

import os


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
