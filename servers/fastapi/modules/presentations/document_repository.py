"""Atomic persistence facade for the additive canonical-document table."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.sql.presentation_document import CanonicalConversionStatus, PresentationDocumentModel
from modules.presentations.domain.conversion_status import (
    MAX_CONVERSION_ATTEMPTS,
    require_conversion_transition,
)
from utils.datetime_utils import get_current_utc_datetime


@dataclass(slots=True)
class CanonicalRevisionConflict(RuntimeError):
    current_revision: int


@dataclass(slots=True)
class CanonicalConversionAttemptsExceeded(RuntimeError):
    attempts: int


async def load_document_record(
    session: AsyncSession, presentation_id: UUID
) -> PresentationDocumentModel | None:
    return await session.scalar(
        select(PresentationDocumentModel).where(
            PresentationDocumentModel.presentation_id == presentation_id
        )
    )


async def write_document_record(
    session: AsyncSession,
    *,
    presentation_id: UUID,
    owner_id: UUID | None,
    document: dict[str, Any],
    checksum: str,
    expected_revision: int,
    status: CanonicalConversionStatus = CanonicalConversionStatus.CONVERTED,
    legacy_source_version: str | None = None,
    asset_mappings: dict[str, str] | None = None,
) -> PresentationDocumentModel:
    if expected_revision < 0:
        raise ValueError("expected_revision must be nonnegative")
    now = get_current_utc_datetime()
    if expected_revision == 0:
        record = PresentationDocumentModel(
            presentation_id=presentation_id,
            owner_id=owner_id,
            schema_version="1.0.0",
            document=document,
            checksum=checksum,
            revision=1,
            conversion_status=status,
            legacy_source_version=legacy_source_version,
            conversion_attempts=1 if legacy_source_version else 0,
            asset_mappings=asset_mappings,
            converted_at=now if status in {CanonicalConversionStatus.CONVERTED, CanonicalConversionStatus.NEEDS_REVIEW} else None,
        )
        session.add(record)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            current = await load_document_record(session, presentation_id)
            raise CanonicalRevisionConflict(current.revision if current else 0) from exc
        await session.refresh(record)
        return record

    existing = await load_document_record(session, presentation_id)
    if existing is None or existing.owner_id != owner_id:
        raise CanonicalRevisionConflict(0)
    require_conversion_transition(existing.conversion_status, status)
    if (
        legacy_source_version is not None
        and existing.conversion_attempts >= MAX_CONVERSION_ATTEMPTS
    ):
        raise CanonicalConversionAttemptsExceeded(existing.conversion_attempts)

    values: dict[str, Any] = {
        "document": document,
        "checksum": checksum,
        "schema_version": "1.0.0",
        "revision": expected_revision + 1,
        "conversion_status": status,
        "conversion_error_code": None,
        "conversion_error_details": None,
        "asset_mappings": asset_mappings,
        "converted_at": now,
        "updated_at": now,
    }
    if legacy_source_version is not None:
        values["legacy_source_version"] = legacy_source_version
        values["conversion_attempts"] = PresentationDocumentModel.conversion_attempts + 1
    statement = (
        update(PresentationDocumentModel)
        .where(
            PresentationDocumentModel.presentation_id == presentation_id,
            PresentationDocumentModel.owner_id == owner_id,
            PresentationDocumentModel.revision == expected_revision,
        )
        .values(**values)
    )
    result = await session.execute(statement)
    if result.rowcount != 1:
        await session.rollback()
        current = await load_document_record(session, presentation_id)
        raise CanonicalRevisionConflict(current.revision if current else 0)
    await session.commit()
    record = await load_document_record(session, presentation_id)
    if record is None:  # Defensive: the owner-scoped record cannot disappear after commit.
        raise CanonicalRevisionConflict(0)
    return record


async def record_conversion_failure(
    session: AsyncSession,
    *,
    presentation_id: UUID,
    owner_id: UUID | None,
    error_code: str,
    legacy_source_version: str,
) -> PresentationDocumentModel:
    """Persist only bounded failure metadata; legacy source remains untouched."""

    code = error_code[:128]
    existing = await load_document_record(session, presentation_id)
    now = get_current_utc_datetime()
    if existing is None:
        record = PresentationDocumentModel(
            presentation_id=presentation_id,
            owner_id=owner_id,
            schema_version="1.0.0",
            document=None,
            checksum=None,
            revision=1,
            conversion_status=CanonicalConversionStatus.FAILED,
            conversion_error_code=code,
            conversion_error_details={"category": "bounded-conversion-failure"},
            legacy_source_version=legacy_source_version,
            conversion_attempts=1,
        )
        session.add(record)
    else:
        require_conversion_transition(
            existing.conversion_status, CanonicalConversionStatus.FAILED
        )
        if existing.conversion_attempts >= MAX_CONVERSION_ATTEMPTS:
            raise CanonicalConversionAttemptsExceeded(existing.conversion_attempts)
        existing.conversion_status = CanonicalConversionStatus.FAILED
        existing.conversion_error_code = code
        existing.conversion_error_details = {"category": "bounded-conversion-failure"}
        existing.legacy_source_version = legacy_source_version
        existing.conversion_attempts += 1
        existing.updated_at = now
        session.add(existing)
        record = existing
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        current = await load_document_record(session, presentation_id)
        if current is None:
            raise
        return current
    await session.refresh(record)
    return record
