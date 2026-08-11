"""Real PostgreSQL workspace isolation for managed assets."""

from __future__ import annotations

import asyncio
import os
import sys
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select

import services.database  # noqa: F401 - install tenant criteria listeners
from api.v1.auth.context import (
    reset_current_owner_id, reset_current_workspace_id,
    set_current_owner_id, set_current_workspace_id,
)
from models.sql.user import User
from modules.assets.domain.models import AssetState
from modules.assets.persistence.models import AssetModel
from modules.workspaces.domain.models import MembershipStatus, Role
from modules.workspaces.persistence.models import MembershipModel, WorkspaceModel


def _url():
    value = os.getenv("MIGRATION_TEST_DATABASE_URL", "")
    if not value.startswith(("postgresql://", "postgresql+psycopg://")):
        pytest.skip("MIGRATION_TEST_DATABASE_URL does not identify disposable PostgreSQL")
    return value


def test_postgresql_managed_assets_are_tenant_scoped(monkeypatch):
    async def scenario():
        engine = create_async_engine(_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        users = [uuid4(), uuid4()]
        workspaces = [uuid4(), uuid4()]
        assets = [uuid4(), uuid4()]
        async with sessions() as session:
            session.add_all([User(id=users[index], username=f"asset-pg-{users[index]}", hashed_password="test") for index in range(2)])
            await session.commit()
            session.add_all([WorkspaceModel(id=workspaces[index], name=f"Asset PG {index}", created_by=users[index]) for index in range(2)])
            await session.commit()
            session.add_all([
                MembershipModel(workspace_id=workspaces[index], user_id=users[index], role=Role.OWNER, status=MembershipStatus.ACTIVE)
                for index in range(2)
            ] + [
                AssetModel(
                    id=assets[index], workspace_id=workspaces[index], owner_id=users[index],
                    storage_provider="local", storage_key=f"workspaces/{workspaces[index]}/assets/{assets[index]}/v000001",
                    size_bytes=1, state=AssetState.READY,
                )
                for index in range(2)
            ])
            await session.commit()
        monkeypatch.setenv("WORKSPACE_RBAC_ENFORCEMENT_ENABLED", "true")
        monkeypatch.setenv("LEGACY_OWNER_BRIDGE_ENABLED", "false")
        owner_token = set_current_owner_id(users[0])
        workspace_token = set_current_workspace_id(workspaces[0])
        try:
            async with sessions() as session:
                visible = list((await session.scalars(select(AssetModel))).all())
                assert [item.id for item in visible] == [assets[0]]
                assert await session.get(AssetModel, assets[1]) is None
        finally:
            reset_current_workspace_id(workspace_token)
            reset_current_owner_id(owner_token)
            await engine.dispose()

    if sys.platform == "win32":
        loop = asyncio.SelectorEventLoop()
        try: loop.run_until_complete(scenario())
        finally: loop.close()
    else:
        asyncio.run(scenario())
