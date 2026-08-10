import asyncio
import copy
import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select

from enums.async_task_status import AsyncTaskStatus
from models.sql.async_task import AsyncTaskModel
from models.sql.presentation import PresentationModel, PresentationVersion
from models.sql.presentation_document import PresentationDocumentModel
from models.sql.presentation_revision import PresentationRevisionModel, PresentationRevisionPatchModel
from models.sql.user import User
from modules.presentations.revision_service import (
    IdempotencyConflictError,
    RevisionConflictError,
    StaleTaskRevisionError,
    apply_revision_commands,
    assert_task_revision_current,
    reconstruct_revision,
    restore_revision,
    write_snapshot_revision,
)


ROOT = Path(__file__).resolve().parents[4]
MINIMAL = json.loads((ROOT / "schemas/presentation-document/fixtures/valid/minimal-en.json").read_text(encoding="utf-8"))


async def database(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'revisions.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        for table in (
            User.__table__, PresentationModel.__table__, PresentationDocumentModel.__table__,
            PresentationRevisionModel.__table__, PresentationRevisionPatchModel.__table__, AsyncTaskModel.__table__,
        ):
            await connection.run_sync(table.create)
    return engine, sessions


def payload_for(presentation_id):
    payload = copy.deepcopy(MINIMAL)
    payload["presentationId"] = str(presentation_id)
    return payload


async def seeded(sessions, *, owner_id=None):
    presentation_id = uuid4()
    async with sessions() as session:
        session.add(PresentationModel(
            id=presentation_id, owner_id=owner_id, version=PresentationVersion.V2_STANDARD,
            content="test", n_slides=1, language="en", title="test",
        ))
        await session.commit()
    async with sessions() as session:
        first = await write_snapshot_revision(
            session, presentation_id=presentation_id, actor_id=owner_id,
            document=payload_for(presentation_id), expected_revision=0,
            idempotency_key="initial", source="test",
        )
    return presentation_id, first


def title_command(payload, title, command_id="title-1"):
    return [{
        "commandId": command_id,
        "type": "UPDATE_SLIDE",
        "targetIds": [payload["slides"][0]["id"]],
        "payload": {"changes": {"title": title}},
    }]


def test_atomic_revision_idempotency_conflict_restore_and_immutability(tmp_path):
    async def scenario():
        engine, sessions = await database(tmp_path)
        presentation_id, first = await seeded(sessions)
        assert first.revision.revision == 1

        commands = title_command(first.document, "Durably saved")
        async with sessions() as session:
            second = await apply_revision_commands(
                session, presentation_id=presentation_id, actor_id=None,
                base_revision=1, commands=commands, idempotency_key="save-1",
            )
            assert second.revision.revision == 2
            assert second.document["slides"][0]["title"] == "Durably saved"

        async with sessions() as session:
            replay = await apply_revision_commands(
                session, presentation_id=presentation_id, actor_id=None,
                base_revision=1, commands=commands, idempotency_key="save-1",
            )
            assert replay.replayed and replay.revision.revision == 2

        async with sessions() as session:
            with pytest.raises(IdempotencyConflictError):
                await apply_revision_commands(
                    session, presentation_id=presentation_id, actor_id=None,
                    base_revision=1, commands=title_command(first.document, "Other", "title-2"),
                    idempotency_key="save-1",
                )
        async with sessions() as session:
            with pytest.raises(RevisionConflictError) as stale:
                await apply_revision_commands(
                    session, presentation_id=presentation_id, actor_id=None,
                    base_revision=1, commands=title_command(first.document, "Stale", "title-3"),
                    idempotency_key="save-stale",
                )
            assert stale.value.current_revision == 2

        async with sessions() as session:
            restored = await restore_revision(
                session, presentation_id=presentation_id, actor_id=None,
                target_revision=1, base_revision=2, idempotency_key="restore-1",
            )
            assert restored.revision.revision == 3
            assert restored.revision.restored_from_revision == 1
            assert restored.document["slides"][0].get("title") == first.document["slides"][0].get("title")
            original = await reconstruct_revision(session, presentation_id, 2)
            assert original["slides"][0]["title"] == "Durably saved"

        async with sessions() as session:
            revision = await session.scalar(select(PresentationRevisionModel).where(PresentationRevisionModel.revision == 2))
            revision.source = "tampered"
            with pytest.raises(ValueError, match="immutable"):
                await session.commit()
            await session.rollback()
        await engine.dispose()
    asyncio.run(scenario())


def test_periodic_anchors_bound_replay_and_checksums_are_deterministic(tmp_path):
    async def scenario():
        engine, sessions = await database(tmp_path)
        presentation_id, result = await seeded(sessions)
        for revision in range(2, 43):
            async with sessions() as session:
                result = await apply_revision_commands(
                    session, presentation_id=presentation_id, actor_id=None,
                    base_revision=revision - 1,
                    commands=title_command(result.document, f"Revision {revision}", f"title-{revision}"),
                    idempotency_key=f"save-{revision}",
                )
        async with sessions() as session:
            anchors = list((await session.scalars(select(PresentationRevisionModel).where(
                PresentationRevisionModel.presentation_id == presentation_id,
                PresentationRevisionModel.snapshot_document.is_not(None),
            ).order_by(PresentationRevisionModel.revision))).all())
            assert [item.revision for item in anchors] == [1, 21, 41]
            replayed = await reconstruct_revision(session, presentation_id, 40)
            replayed_again = await reconstruct_revision(session, presentation_id, 40)
            assert replayed == replayed_again
            assert replayed["slides"][0]["title"] == "Revision 40"
        await engine.dispose()
    asyncio.run(scenario())


def test_cross_owner_revision_write_is_denied_and_stale_job_is_rejected(tmp_path):
    async def scenario():
        engine, sessions = await database(tmp_path)
        owner_id, attacker_id = uuid4(), uuid4()
        async with sessions() as session:
            session.add_all([
                User(id=owner_id, username="owner", hashed_password="x"),
                User(id=attacker_id, username="attacker", hashed_password="x"),
            ])
            await session.commit()
        presentation_id, first = await seeded(sessions, owner_id=owner_id)
        async with sessions() as session:
            from modules.presentations.revision_service import RevisionNotFoundError
            with pytest.raises(RevisionNotFoundError):
                await apply_revision_commands(
                    session, presentation_id=presentation_id, actor_id=attacker_id,
                    base_revision=1, commands=title_command(first.document, "Attack"),
                    idempotency_key="attack",
                )
        async with sessions() as session:
            current = await apply_revision_commands(
                session, presentation_id=presentation_id, actor_id=owner_id,
                base_revision=1, commands=title_command(first.document, "Owner edit"),
                idempotency_key="owner-edit",
            )
            task = AsyncTaskModel(
                owner_id=owner_id, actor_id=owner_id, presentation_id=presentation_id,
                source_revision=1, type="export", status=AsyncTaskStatus.PENDING,
            )
            session.add(task); await session.commit()
            with pytest.raises(StaleTaskRevisionError) as stale:
                await assert_task_revision_current(session, task)
            assert stale.value.current_revision == current.revision.revision
        await engine.dispose()
    asyncio.run(scenario())
