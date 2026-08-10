"""PostgreSQL-only concurrency and tenant-boundary integration coverage."""

from __future__ import annotations

import asyncio
import copy
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select

import services.database  # noqa: F401 - installs global ORM tenant criteria
from api.v1.auth.context import (
    reset_current_owner_id,
    reset_current_workspace_id,
    set_current_owner_id,
    set_current_workspace_id,
)
from enums.async_task_status import AsyncTaskStatus
from models.sql.async_task import AsyncTaskModel
from models.sql.image_asset import ImageAsset
from models.sql.presentation import PresentationModel, PresentationVersion
from models.sql.template import TemplateModel
from models.sql.user import User
from modules.presentations.revision_service import (
    RevisionConflictError,
    apply_revision_commands,
    write_snapshot_revision,
)
from modules.workspaces.domain.models import MembershipStatus, Role
from modules.workspaces.persistence.models import MembershipModel, WorkspaceModel


ROOT = Path(__file__).resolve().parents[4]
MINIMAL = json.loads(
    (ROOT / "schemas/presentation-document/fixtures/valid/minimal-en.json").read_text(
        encoding="utf-8"
    )
)


def _postgres_url() -> str:
    url = os.getenv("MIGRATION_TEST_DATABASE_URL", "")
    if not url.startswith(("postgresql://", "postgresql+psycopg://")):
        pytest.skip("MIGRATION_TEST_DATABASE_URL does not identify disposable PostgreSQL")
    return url


def _document(presentation_id):
    document = copy.deepcopy(MINIMAL)
    document["presentationId"] = str(presentation_id)
    return document


def _title_command(document, title: str, command_id: str):
    return [{
        "commandId": command_id,
        "type": "UPDATE_SLIDE",
        "targetIds": [document["slides"][0]["id"]],
        "payload": {"changes": {"title": title}},
    }]


def test_postgresql_serializes_revision_writes_and_scopes_owned_resources(monkeypatch):
    async def scenario():
        engine = create_async_engine(_postgres_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        user_a, user_b = uuid4(), uuid4()
        workspace_a, workspace_b = uuid4(), uuid4()
        presentation_a, presentation_b = uuid4(), uuid4()

        async with sessions() as session:
            session.add_all([
                User(id=user_a, username=f"pg-a-{user_a}", hashed_password="test"),
                User(id=user_b, username=f"pg-b-{user_b}", hashed_password="test"),
            ])
            await session.commit()
            session.add_all([
                WorkspaceModel(id=workspace_a, name="PostgreSQL A", created_by=user_a),
                WorkspaceModel(id=workspace_b, name="PostgreSQL B", created_by=user_b),
            ])
            await session.commit()
            session.add_all([
                MembershipModel(
                    workspace_id=workspace_a, user_id=user_a, role=Role.OWNER,
                    status=MembershipStatus.ACTIVE,
                ),
                MembershipModel(
                    workspace_id=workspace_b, user_id=user_b, role=Role.OWNER,
                    status=MembershipStatus.ACTIVE,
                ),
                PresentationModel(
                    id=presentation_a, owner_id=user_a, workspace_id=workspace_a,
                    version=PresentationVersion.V2_STANDARD, content="a", n_slides=1,
                    language="en",
                ),
                PresentationModel(
                    id=presentation_b, owner_id=user_b, workspace_id=workspace_b,
                    version=PresentationVersion.V2_STANDARD, content="b", n_slides=1,
                    language="en",
                ),
                ImageAsset(owner_id=user_a, workspace_id=workspace_a, path="pg-a"),
                ImageAsset(owner_id=user_b, workspace_id=workspace_b, path="pg-b"),
                TemplateModel(owner_id=user_a, workspace_id=workspace_a, name="pg-a"),
                TemplateModel(owner_id=user_b, workspace_id=workspace_b, name="pg-b"),
            ])
            await session.commit()
            session.add_all([
                AsyncTaskModel(
                    id=f"pg-a-{presentation_a}", owner_id=user_a, workspace_id=workspace_a,
                    actor_id=user_a, presentation_id=presentation_a, resource_id=str(presentation_a),
                    type="export", status=AsyncTaskStatus.PENDING,
                ),
                AsyncTaskModel(
                    id=f"pg-b-{presentation_b}", owner_id=user_b, workspace_id=workspace_b,
                    actor_id=user_b, presentation_id=presentation_b, resource_id=str(presentation_b),
                    type="export", status=AsyncTaskStatus.PENDING,
                ),
            ])
            await session.commit()

        async with sessions() as session:
            initial = await write_snapshot_revision(
                session, presentation_id=presentation_a, actor_id=user_a,
                document=_document(presentation_a), expected_revision=0,
                idempotency_key="pg-initial", source="postgres-test",
            )

        async def write(title: str, key: str):
            async with sessions() as session:
                return await apply_revision_commands(
                    session, presentation_id=presentation_a, actor_id=user_a,
                    base_revision=1,
                    commands=_title_command(initial.document, title, key),
                    idempotency_key=key,
                )

        results = await asyncio.gather(
            write("winner-a", "pg-race-a"),
            write("winner-b", "pg-race-b"),
            return_exceptions=True,
        )
        assert sum(not isinstance(item, Exception) for item in results) == 1
        conflicts = [item for item in results if isinstance(item, RevisionConflictError)]
        assert len(conflicts) == 1
        assert conflicts[0].current_revision == 2

        monkeypatch.setenv("WORKSPACE_RBAC_ENFORCEMENT_ENABLED", "true")
        monkeypatch.setenv("LEGACY_OWNER_BRIDGE_ENABLED", "false")
        owner_token = set_current_owner_id(user_a)
        workspace_token = set_current_workspace_id(workspace_a)
        try:
            async with sessions() as session:
                assert [row.id for row in (await session.scalars(select(PresentationModel))).all()] == [presentation_a]
                assert [row.workspace_id for row in (await session.scalars(select(ImageAsset))).all()] == [workspace_a]
                assert [row.workspace_id for row in (await session.scalars(select(TemplateModel))).all()] == [workspace_a]
                assert [row.workspace_id for row in (await session.scalars(select(AsyncTaskModel))).all()] == [workspace_a]
        finally:
            reset_current_workspace_id(workspace_token)
            reset_current_owner_id(owner_token)
            await engine.dispose()

    if sys.platform == "win32":
        loop = asyncio.SelectorEventLoop()
        try:
            loop.run_until_complete(scenario())
        finally:
            loop.close()
    else:
        asyncio.run(scenario())
