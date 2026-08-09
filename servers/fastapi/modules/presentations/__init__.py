"""Stable presentation application boundary.

HTTP handlers should depend on this package; this package must not depend on
FastAPI request objects or provider-specific SDK/configuration objects.
"""

from .repository import (
    delete_presentation_record,
    duplicate_presentation_record,
    load_presentation_with_slides,
    list_presentation_rows,
)
from .shadow_read import record_shadow_parity_if_enabled

__all__ = [
    "delete_presentation_record",
    "duplicate_presentation_record",
    "load_presentation_with_slides",
    "list_presentation_rows",
    "record_shadow_parity_if_enabled",
]
