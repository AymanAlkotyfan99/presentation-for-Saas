"""Privacy-safe canonical-document telemetry with a finite metadata vocabulary."""

import json
import logging
from typing import Any


logger = logging.getLogger(__name__)
ALLOWED_EVENTS = {
    "conversion_attempt", "conversion_success", "conversion_failure",
    "conversion_unsupported", "validation_failure", "shadow_parity",
    "checksum_mismatch", "revision_conflict", "legacy_fallback",
}
ALLOWED_FIELDS = {
    "schema_version", "legacy_version", "error_code", "conversion_result",
    "parity_status", "document_size_bucket", "slide_count_bucket",
    "element_count_bucket", "supported_categories", "unsupported_categories",
}


def count_bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value <= 10:
        return "1-10"
    if value <= 50:
        return "11-50"
    if value <= 200:
        return "51-200"
    if value <= 1000:
        return "201-1000"
    return "1001+"


def size_bucket(value: int) -> str:
    if value <= 64 * 1024:
        return "<=64KiB"
    if value <= 512 * 1024:
        return "64-512KiB"
    if value <= 2 * 1024 * 1024:
        return "512KiB-2MiB"
    return ">2MiB"


def record_canonical_metric(event: str, **metadata: Any) -> dict[str, Any]:
    if event not in ALLOWED_EVENTS:
        raise ValueError("Unknown canonical metric event")
    payload: dict[str, Any] = {"event": event}
    for key, value in metadata.items():
        if key not in ALLOWED_FIELDS:
            continue
        if isinstance(value, (str, int, bool)):
            payload[key] = value
        elif isinstance(value, (list, tuple)):
            payload[key] = [str(item)[:64] for item in value[:32]]
    logger.info("canonical_document_metric %s", json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return payload
