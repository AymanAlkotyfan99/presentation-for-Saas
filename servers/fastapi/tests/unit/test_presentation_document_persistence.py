import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models.sql.presentation import PresentationModel, PresentationVersion
from models.sql.presentation_document import PresentationDocumentModel
from models.sql.user import User  # noqa: F401 - resolves owner FK types for isolated DDL
from modules.presentations.document_repository import (
    CanonicalConversionAttemptsExceeded,
    CanonicalRevisionConflict,
    load_document_record,
    record_conversion_failure,
    write_document_record,
)
from modules.presentations.domain import CanonicalValidationError, canonical_checksum, validate_presentation_document


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
MINIMAL = json.loads((REPOSITORY_ROOT / "schemas/presentation-document/fixtures/valid/minimal-en.json").read_text(encoding="utf-8"))


def test_atomic_revision_and_validation_preserve_previous_document(tmp_path):
    async def scenario():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'canonical.db'}")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(PresentationModel.__table__.create)
            await connection.run_sync(PresentationDocumentModel.__table__.create)
        presentation_id = uuid4()
        async with sessions() as session:
            session.add(PresentationModel(
                id=presentation_id,
                version=PresentationVersion.V2_STANDARD,
                content="test",
                n_slides=1,
                language="en",
                title="test",
            ))
            await session.commit()

        payload = json.loads(json.dumps(MINIMAL))
        payload["presentationId"] = str(presentation_id)
        document = validate_presentation_document(payload)
        async with sessions() as session:
            first = await write_document_record(
                session,
                presentation_id=presentation_id,
                owner_id=None,
                document=document.model_dump(mode="json", by_alias=True, exclude_none=True),
                checksum=canonical_checksum(document),
                expected_revision=0,
            )
            assert first.revision == 1

        updated_payload = json.loads(json.dumps(payload))
        updated_payload["title"] = "Updated title"
        updated = validate_presentation_document(updated_payload)
        async with sessions() as session:
            second = await write_document_record(
                session,
                presentation_id=presentation_id,
                owner_id=None,
                document=updated.model_dump(mode="json", by_alias=True, exclude_none=True),
                checksum=canonical_checksum(updated),
                expected_revision=1,
            )
            assert second.revision == 2
            saved_checksum = second.checksum

        async with sessions() as session:
            with pytest.raises(CanonicalRevisionConflict) as conflict:
                await write_document_record(
                    session,
                    presentation_id=presentation_id,
                    owner_id=None,
                    document=document.model_dump(mode="json", by_alias=True, exclude_none=True),
                    checksum=canonical_checksum(document),
                    expected_revision=1,
                )
            assert conflict.value.current_revision == 2

        invalid = json.loads(json.dumps(updated_payload))
        invalid["title"] = "<script>unsafe</script>"
        with pytest.raises(CanonicalValidationError):
            validate_presentation_document(invalid)
        async with sessions() as session:
            persisted = await load_document_record(session, presentation_id)
            assert persisted.revision == 2
            assert persisted.checksum == saved_checksum

        await engine.dispose()

    asyncio.run(scenario())


def test_table_declares_one_current_document_and_nonnegative_revision_constraints():
    constraint_names = {constraint.name for constraint in PresentationDocumentModel.__table__.constraints}
    assert "uq_presentation_documents_presentation_id" in constraint_names
    assert "ck_presentation_documents_revision" in constraint_names
    assert "ck_presentation_documents_attempts" in constraint_names
    assert "ck_presentation_documents_schema_version" in constraint_names
    assert "ck_presentation_documents_payload_checksum" in constraint_names


def test_conversion_retries_are_bounded_and_state_transitions_are_enforced(tmp_path):
    async def scenario():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'attempts.db'}")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(PresentationModel.__table__.create)
            await connection.run_sync(PresentationDocumentModel.__table__.create)
        presentation_id = uuid4()
        async with sessions() as session:
            session.add(
                PresentationModel(
                    id=presentation_id,
                    version=PresentationVersion.V2_STANDARD,
                    content="test",
                    n_slides=1,
                    language="en",
                    title="test",
                )
            )
            await session.commit()
        for expected_attempt in range(1, 4):
            async with sessions() as session:
                record = await record_conversion_failure(
                    session,
                    presentation_id=presentation_id,
                    owner_id=None,
                    error_code="CANONICAL_TEST_FAILURE",
                    legacy_source_version="v2",
                )
                assert record.conversion_attempts == expected_attempt
        async with sessions() as session:
            with pytest.raises(CanonicalConversionAttemptsExceeded) as exhausted:
                await record_conversion_failure(
                    session,
                    presentation_id=presentation_id,
                    owner_id=None,
                    error_code="CANONICAL_TEST_FAILURE",
                    legacy_source_version="v2",
                )
            assert exhausted.value.attempts == 3
        await engine.dispose()

    asyncio.run(scenario())
