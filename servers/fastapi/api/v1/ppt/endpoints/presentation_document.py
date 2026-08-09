"""Additive APIs for the controlled canonical-document rollout."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from api.operation_security import operation_guard
from api.v1.auth.context import get_current_owner_id
from models.sql.image_asset import ImageAsset
from models.sql.presentation import PresentationModel
from models.sql.presentation_document import CanonicalConversionStatus, PresentationDocumentModel
from modules.presentations.document_repository import (
    CanonicalConversionAttemptsExceeded,
    CanonicalRevisionConflict,
    load_document_record,
    record_conversion_failure,
    write_document_record,
)
from modules.presentations.domain import (
    CanonicalValidationError,
    canonical_checksum,
    validate_presentation_document,
)
from modules.presentations.domain.document import PresentationDocument
from modules.presentations.domain.conversion_status import MAX_CONVERSION_ATTEMPTS
from modules.presentations.migrations.legacy_document import ConversionPreview, convert_legacy_presentation
from modules.presentations.observability import count_bucket, record_canonical_metric, size_bucket
from modules.presentations.repository import load_presentation_with_slides
from modules.presentations.shadow_parity import compare_shadow_parity
from services.database import get_async_session
from utils.api_errors import StableAPIError
from utils.architecture_flags import (
    canonical_document_reads_enabled,
    canonical_document_writes_enabled,
    canonical_internal_cohort_allows,
    canonical_shadow_render_enabled,
    legacy_document_fallback_enabled,
)


PRESENTATION_DOCUMENT_ROUTER = APIRouter(prefix="/presentations", tags=["Presentation Document"])


class CanonicalResponseModel(BaseModel):
    schema_version: Literal["1.0.0"]
    revision: int
    checksum: str
    conversion_status: CanonicalConversionStatus
    source: Literal["persisted", "legacy-fallback"]
    document: PresentationDocument
    shadow_parity: str | None = None

    model_config = ConfigDict(alias_generator=lambda value: "".join([value.split("_")[0]] + [part.title() for part in value.split("_")[1:]]), populate_by_name=True)


class MigrationPreviewModel(BaseModel):
    convertible: bool
    schema_version: Literal["1.0.0"]
    conversion_status: CanonicalConversionStatus
    warnings: list[str]
    unsupported_features: list[str]
    expected_asset_mappings: list[dict[str, str | bool]]
    checksum: str
    document_size_bytes: int

    model_config = ConfigDict(alias_generator=lambda value: "".join([value.split("_")[0]] + [part.title() for part in value.split("_")[1:]]), populate_by_name=True)


def _require_flag(enabled: bool, code: str) -> None:
    if not enabled:
        raise StableAPIError(404, code, "Canonical document endpoint is not enabled")


def _require_cohort(presentation: PresentationModel) -> None:
    if not canonical_internal_cohort_allows(presentation.id, presentation.owner_id):
        raise StableAPIError(403, "CANONICAL_COHORT_REQUIRED", "Presentation is not in the canonical internal cohort")


async def _load_presentation(
    session: AsyncSession, presentation_id: UUID
) -> tuple[PresentationModel, list[Any]]:
    presentation, slides = await load_presentation_with_slides(session, presentation_id)
    if presentation is None or presentation.owner_id != get_current_owner_id():
        raise StableAPIError(404, "PRESENTATION_NOT_FOUND", "Presentation not found")
    return presentation, slides


def _parse_if_match(value: str | None) -> int:
    if value is None:
        raise StableAPIError(428, "CANONICAL_REVISION_REQUIRED", "If-Match revision is required")
    candidate = value.strip()
    if candidate.startswith("W/"):
        candidate = candidate[2:]
    candidate = candidate.strip('"')
    if not candidate.isdigit():
        raise StableAPIError(400, "CANONICAL_REVISION_INVALID", "If-Match revision is invalid")
    return int(candidate)


def _record_response(record: PresentationDocumentModel, response: Response, *, shadow: str | None = None) -> CanonicalResponseModel:
    if record.document is None or record.checksum is None:
        raise StableAPIError(
            409,
            record.conversion_error_code or "CANONICAL_CONVERSION_FAILED",
            "Canonical document conversion has not completed",
            params={"conversionStatus": record.conversion_status.value},
        )
    response.headers["ETag"] = f'"{record.revision}"'
    return CanonicalResponseModel(
        schemaVersion="1.0.0",
        revision=record.revision,
        checksum=record.checksum,
        conversionStatus=record.conversion_status,
        source="persisted",
        document=validate_presentation_document(record.document),
        shadowParity=shadow,
    )


def _preview_response(preview: ConversionPreview) -> MigrationPreviewModel:
    size = len(preview.document.model_dump_json(by_alias=True, exclude_none=True).encode("utf-8"))
    return MigrationPreviewModel(
        convertible=preview.status != CanonicalConversionStatus.UNSUPPORTED,
        schemaVersion="1.0.0",
        conversionStatus=preview.status,
        warnings=preview.warnings,
        unsupportedFeatures=preview.unsupported_features,
        expectedAssetMappings=preview.safe_asset_summary(),
        checksum=preview.checksum,
        documentSizeBytes=size,
    )


async def _validate_asset_ownership(
    session: AsyncSession,
    document: PresentationDocument,
    existing: PresentationDocumentModel | None,
) -> None:
    referenced = {asset.asset_id for asset in document.assets}
    if not referenced:
        return
    owner_id = get_current_owner_id()
    owner_predicate = ImageAsset.owner_id.is_(None) if owner_id is None else ImageAsset.owner_id == owner_id
    owned = set(await session.scalars(
        select(ImageAsset.id).where(ImageAsset.id.in_(referenced), owner_predicate)
    ))
    compatibility = {
        UUID(asset_id)
        for asset_id in (existing.asset_mappings or {})
        if _is_uuid(asset_id)
    } if existing else set()
    if referenced - owned - compatibility:
        raise StableAPIError(403, "CANONICAL_ASSET_ACCESS_DENIED", "One or more asset references are not available")


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except ValueError:
        return False


def _validate_payload(payload: Any, presentation_id: UUID) -> PresentationDocument:
    try:
        document = validate_presentation_document(payload)
    except CanonicalValidationError as exc:
        record_canonical_metric("validation_failure", schema_version="1.0.0", error_code=exc.code)
        raise StableAPIError(422, exc.code, exc.detail, params=exc.params) from exc
    if document.presentation_id != presentation_id:
        raise StableAPIError(422, "CANONICAL_PRESENTATION_ID_MISMATCH", "Document presentationId does not match the route")
    return document


@PRESENTATION_DOCUMENT_ROUTER.get("/{presentation_id}/document", response_model=CanonicalResponseModel, response_model_by_alias=True, response_model_exclude_none=True)
async def get_presentation_document(
    presentation_id: UUID,
    response: Response,
    session: AsyncSession = Depends(get_async_session),
):
    _require_flag(canonical_document_reads_enabled(), "CANONICAL_READ_DISABLED")
    presentation, slides = await _load_presentation(session, presentation_id)
    _require_cohort(presentation)
    record = await load_document_record(session, presentation_id)
    if record is None:
        if not legacy_document_fallback_enabled():
            raise StableAPIError(404, "CANONICAL_DOCUMENT_NOT_FOUND", "Canonical document not found")
        async with operation_guard("canonical_document_conversion"):
            preview = convert_legacy_presentation(presentation, slides)
        record_canonical_metric("legacy_fallback", schema_version="1.0.0", legacy_version=presentation.version.value)
        response.headers["ETag"] = '"0"'
        return CanonicalResponseModel(
            schemaVersion="1.0.0", revision=0, checksum=preview.checksum,
            conversionStatus=preview.status, source="legacy-fallback", document=preview.document,
        )
    shadow = None
    if canonical_shadow_render_enabled() and record.document is not None:
        shadow = compare_shadow_parity(presentation, slides, validate_presentation_document(record.document)).status
    return _record_response(record, response, shadow=shadow)


@PRESENTATION_DOCUMENT_ROUTER.put("/{presentation_id}/document", response_model=CanonicalResponseModel, response_model_by_alias=True, response_model_exclude_none=True)
async def put_presentation_document(
    presentation_id: UUID,
    response: Response,
    payload: Annotated[dict[str, Any], Body()],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    session: AsyncSession = Depends(get_async_session),
):
    _require_flag(canonical_document_writes_enabled(), "CANONICAL_WRITE_DISABLED")
    presentation, _slides = await _load_presentation(session, presentation_id)
    _require_cohort(presentation)
    expected_revision = _parse_if_match(if_match)
    document = _validate_payload(payload, presentation_id)
    existing = await load_document_record(session, presentation_id)
    await _validate_asset_ownership(session, document, existing)
    status = CanonicalConversionStatus.NEEDS_REVIEW if document.compatibility.requires_legacy_renderer else CanonicalConversionStatus.CONVERTED
    try:
        record = await write_document_record(
            session, presentation_id=presentation_id, owner_id=get_current_owner_id(),
            document=document.model_dump(mode="json", by_alias=True, exclude_none=True),
            checksum=canonical_checksum(document), expected_revision=expected_revision,
            status=status,
            asset_mappings=existing.asset_mappings if existing else None,
        )
    except CanonicalRevisionConflict as exc:
        record_canonical_metric("revision_conflict", schema_version="1.0.0")
        raise StableAPIError(409, "CANONICAL_REVISION_CONFLICT", "Canonical document revision is stale", params={"currentRevision": exc.current_revision}) from exc
    return _record_response(record, response)


@PRESENTATION_DOCUMENT_ROUTER.post("/{presentation_id}/document/migration-preview", response_model=MigrationPreviewModel, response_model_by_alias=True, response_model_exclude_none=True)
async def preview_presentation_migration(
    presentation_id: UUID,
    session: AsyncSession = Depends(get_async_session),
):
    presentation, slides = await _load_presentation(session, presentation_id)
    try:
        async with operation_guard("canonical_document_conversion"):
            preview = convert_legacy_presentation(presentation, slides)
    except CanonicalValidationError as exc:
        record_canonical_metric("conversion_failure", schema_version="1.0.0", error_code=exc.code)
        raise StableAPIError(422, exc.code, "Legacy presentation could not be converted") from exc
    return _preview_response(preview)


@PRESENTATION_DOCUMENT_ROUTER.post("/{presentation_id}/document/convert", response_model=CanonicalResponseModel, response_model_by_alias=True, response_model_exclude_none=True)
async def convert_presentation_document(
    presentation_id: UUID,
    response: Response,
    session: AsyncSession = Depends(get_async_session),
):
    _require_flag(canonical_document_writes_enabled(), "CANONICAL_WRITE_DISABLED")
    presentation, slides = await _load_presentation(session, presentation_id)
    _require_cohort(presentation)
    existing = await load_document_record(session, presentation_id)
    if existing and existing.conversion_status == CanonicalConversionStatus.CONVERTED:
        return _record_response(existing, response)
    if existing and existing.conversion_attempts >= MAX_CONVERSION_ATTEMPTS:
        raise StableAPIError(
            409,
            "CANONICAL_CONVERSION_ATTEMPTS_EXHAUSTED",
            "Canonical conversion retry limit has been reached",
            params={"attempts": existing.conversion_attempts},
        )
    record_canonical_metric("conversion_attempt", schema_version="1.0.0", legacy_version=presentation.version.value)
    try:
        async with operation_guard("canonical_document_conversion"):
            preview = convert_legacy_presentation(presentation, slides)
    except CanonicalValidationError as exc:
        await record_conversion_failure(
            session,
            presentation_id=presentation_id,
            owner_id=get_current_owner_id(),
            error_code=exc.code,
            legacy_source_version=presentation.version.value,
        )
        record_canonical_metric("conversion_failure", schema_version="1.0.0", error_code=exc.code)
        raise StableAPIError(422, exc.code, "Legacy presentation could not be converted") from exc
    document_payload = preview.document.model_dump(mode="json", by_alias=True, exclude_none=True)
    try:
        record = await write_document_record(
            session, presentation_id=presentation_id, owner_id=get_current_owner_id(),
            document=document_payload, checksum=preview.checksum,
            expected_revision=existing.revision if existing else 0,
            status=preview.status, legacy_source_version=presentation.version.value,
            asset_mappings=preview.asset_mappings,
        )
    except CanonicalConversionAttemptsExceeded as exc:
        raise StableAPIError(
            409,
            "CANONICAL_CONVERSION_ATTEMPTS_EXHAUSTED",
            "Canonical conversion retry limit has been reached",
            params={"attempts": exc.attempts},
        ) from exc
    except CanonicalRevisionConflict as exc:
        record_canonical_metric("revision_conflict", schema_version="1.0.0")
        raise StableAPIError(409, "CANONICAL_REVISION_CONFLICT", "Canonical document changed during conversion", params={"currentRevision": exc.current_revision}) from exc
    event = "conversion_success" if preview.status == CanonicalConversionStatus.CONVERTED else "conversion_unsupported"
    record_canonical_metric(
        event,
        schema_version="1.0.0",
        conversion_result=preview.status.value,
        document_size_bucket=size_bucket(len(preview.document.model_dump_json(by_alias=True).encode("utf-8"))),
        slide_count_bucket=count_bucket(len(preview.document.slides)),
    )
    return _record_response(record, response)
