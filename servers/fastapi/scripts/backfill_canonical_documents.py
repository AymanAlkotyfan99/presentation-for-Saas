"""Bounded administrator CLI for resumable canonical-document backfill.

Dry-run is the default. Use --execute only after reviewing preview summaries.
This is intentionally synchronous/bounded until Sprint 8 provides workers.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from uuid import UUID

from sqlmodel import select

from models.sql.presentation import PresentationModel
from models.sql.presentation_document import CanonicalConversionStatus
from modules.presentations.document_repository import (
    CanonicalConversionAttemptsExceeded,
    CanonicalRevisionConflict,
    load_document_record,
    record_conversion_failure,
    write_document_record,
)
from modules.presentations.domain import CanonicalValidationError
from modules.presentations.domain.conversion_status import MAX_CONVERSION_ATTEMPTS
from modules.presentations.migrations.legacy_document import convert_legacy_presentation
from modules.presentations.repository import load_presentation_with_slides
from services.database import async_session_maker, dispose_engines


@dataclass
class Summary:
    dry_run: bool
    inspected: int = 0
    converted: int = 0
    needs_review: int = 0
    failed: int = 0
    skipped: int = 0
    conflicts: int = 0
    attempts_exhausted: int = 0
    last_cursor: str | None = None
    stopped_on_error_threshold: bool = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--start-after", type=UUID)
    parser.add_argument("--max-records", type=int, default=100)
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--systemic-error-threshold", type=int, default=5)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Preview only (default)")
    mode.add_argument("--execute", action="store_true", help="Persist converted documents")
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 100:
        parser.error("--batch-size must be between 1 and 100")
    if not 1 <= args.max_records <= 10_000:
        parser.error("--max-records must be between 1 and 10000")
    if not 1 <= args.systemic_error_threshold <= 100:
        parser.error("--systemic-error-threshold must be between 1 and 100")
    return args


async def _candidate_ids(cursor: UUID | None, limit: int) -> list[UUID]:
    async with async_session_maker() as session:
        statement = select(PresentationModel.id).order_by(PresentationModel.id).limit(limit)
        if cursor is not None:
            statement = statement.where(PresentationModel.id > cursor)
        return list(await session.scalars(statement))


async def run(args: argparse.Namespace) -> Summary:
    summary = Summary(dry_run=not args.execute)
    cursor = args.start_after
    systemic_errors = 0
    while summary.inspected < args.max_records:
        ids = await _candidate_ids(cursor, min(args.batch_size, args.max_records - summary.inspected))
        if not ids:
            break
        for presentation_id in ids:
            cursor = presentation_id
            summary.last_cursor = str(cursor)
            summary.inspected += 1
            async with async_session_maker() as session:
                presentation, slides = await load_presentation_with_slides(session, presentation_id)
                if presentation is None:
                    summary.skipped += 1
                    continue
                existing = await load_document_record(session, presentation_id)
                if (
                    existing
                    and existing.conversion_attempts >= MAX_CONVERSION_ATTEMPTS
                    and existing.conversion_status != CanonicalConversionStatus.CONVERTED
                ):
                    summary.attempts_exhausted += 1
                    continue
                if existing and (
                    existing.conversion_status in {CanonicalConversionStatus.CONVERTED, CanonicalConversionStatus.NEEDS_REVIEW}
                    or (existing.conversion_status == CanonicalConversionStatus.FAILED and not args.retry_failed)
                ):
                    summary.skipped += 1
                    continue
                try:
                    preview = convert_legacy_presentation(presentation, slides)
                    if args.execute:
                        await write_document_record(
                            session,
                            presentation_id=presentation.id,
                            owner_id=presentation.owner_id,
                            document=preview.document.model_dump(mode="json", by_alias=True, exclude_none=True),
                            checksum=preview.checksum,
                            expected_revision=existing.revision if existing else 0,
                            status=preview.status,
                            legacy_source_version=presentation.version.value,
                            asset_mappings=preview.asset_mappings,
                        )
                    if preview.status == CanonicalConversionStatus.CONVERTED:
                        summary.converted += 1
                    else:
                        summary.needs_review += 1
                    systemic_errors = 0
                except CanonicalRevisionConflict:
                    summary.conflicts += 1
                except CanonicalConversionAttemptsExceeded:
                    summary.attempts_exhausted += 1
                except CanonicalValidationError as exc:
                    summary.failed += 1
                    systemic_errors += 1
                    if args.execute:
                        await record_conversion_failure(
                            session,
                            presentation_id=presentation.id,
                            owner_id=presentation.owner_id,
                            error_code=exc.code,
                            legacy_source_version=presentation.version.value,
                        )
                except Exception:
                    summary.failed += 1
                    systemic_errors += 1
                    if args.execute:
                        await record_conversion_failure(
                            session,
                            presentation_id=presentation.id,
                            owner_id=presentation.owner_id,
                            error_code="CANONICAL_CONVERSION_INTERNAL",
                            legacy_source_version=presentation.version.value,
                        )
                if systemic_errors >= args.systemic_error_threshold:
                    summary.stopped_on_error_threshold = True
                    return summary
        if len(ids) < args.batch_size:
            break
    return summary


async def main() -> None:
    args = parse_args()
    try:
        summary = await run(args)
        print(json.dumps(asdict(summary), sort_keys=True, separators=(",", ":")))
    finally:
        await dispose_engines()


if __name__ == "__main__":
    asyncio.run(main())
