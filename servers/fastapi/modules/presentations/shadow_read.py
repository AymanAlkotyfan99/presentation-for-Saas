"""Fail-safe shadow comparison invoked from the authoritative legacy read path."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from models.sql.presentation import PresentationModel
from models.sql.slide import SlideModel
from modules.presentations.document_repository import load_document_record
from modules.presentations.domain import (
    CanonicalValidationError,
    validate_presentation_document,
)
from modules.presentations.observability import record_canonical_metric
from modules.presentations.shadow_parity import compare_shadow_parity
from utils.architecture_flags import (
    canonical_internal_cohort_allows,
    canonical_shadow_render_enabled,
)


async def record_shadow_parity_if_enabled(
    session: AsyncSession,
    presentation: PresentationModel,
    slides: list[SlideModel],
) -> None:
    """Compare structures without changing or delaying the legacy response contract."""

    if not canonical_shadow_render_enabled() or not canonical_internal_cohort_allows(
        presentation.id, presentation.owner_id
    ):
        return
    record = await load_document_record(session, presentation.id)
    if record is None or record.document is None:
        return
    try:
        document = validate_presentation_document(record.document)
        compare_shadow_parity(presentation, slides, document)
    except CanonicalValidationError as exc:
        record_canonical_metric(
            "validation_failure",
            schema_version=record.schema_version,
            error_code=exc.code,
        )
    except Exception:
        # Shadow work is observational. A bounded generic signal is useful, but
        # it must never expose content or break the authoritative legacy read.
        record_canonical_metric(
            "conversion_failure",
            schema_version=record.schema_version,
            error_code="CANONICAL_SHADOW_INTERNAL",
        )
