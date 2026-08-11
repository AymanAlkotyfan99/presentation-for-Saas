"""Real PostgreSQL tenant criteria coverage for provider accounts."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select

import services.database  # noqa: F401 - install workspace criteria listeners
from api.v1.auth.context import reset_current_owner_id, reset_current_workspace_id, set_current_owner_id, set_current_workspace_id
from models.sql.user import User
from modules.providers.domain.contracts import RegionPolicyStatus
from modules.providers.persistence.models import (
    EncryptedProviderSecretModel,
    ProviderAccountModel,
    ProviderCircuitModel,
    ProviderSnapshotModel,
    ProviderUsageModel,
)
from modules.providers.security.secrets import (
    SecretDecryptionError,
    delete_provider_secret,
    resolve_provider_secret,
    rotate_provider_secret,
)
from modules.providers.tests.test_providers import (
    FakeAdapter,
    StaticKeys,
    add_account,
)
from modules.providers.adapters.registry import ProviderRegistry
from modules.providers.application.circuit import allow_call, record_failure, record_success
from modules.providers.application.executor import ProviderExecutor
from modules.providers.domain.contracts import (
    CapabilityFamily,
    CircuitState,
    TextAIRequest,
    TextAIResult,
    TextMessage,
)
from modules.workspaces.persistence.models import WorkspaceModel
from utils.datetime_utils import get_current_utc_datetime


def _url() -> str:
    value = os.getenv("MIGRATION_TEST_DATABASE_URL", "")
    if not value.startswith(("postgresql://", "postgresql+psycopg://")):
        pytest.skip("MIGRATION_TEST_DATABASE_URL does not identify disposable PostgreSQL")
    return value


def test_postgresql_provider_accounts_are_tenant_scoped(monkeypatch):
    async def scenario():
        engine = create_async_engine(_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        users = [uuid4(), uuid4()]; workspaces = [uuid4(), uuid4()]; accounts = [uuid4(), uuid4()]
        async with sessions() as session:
            session.add_all([User(id=users[i], username=f"provider-pg-{users[i]}", hashed_password="test") for i in range(2)])
            await session.commit()
            session.add_all([WorkspaceModel(id=workspaces[i], name=f"Provider PG {i}", created_by=users[i]) for i in range(2)])
            await session.commit()
            session.add_all([ProviderAccountModel(id=accounts[i], workspace_id=workspaces[i], owner_id=users[i], adapter_id="text.ollama", name=f"Provider {i}", region_policy_status=RegionPolicyStatus.ALLOWED) for i in range(2)])
            await session.commit()
        monkeypatch.setenv("WORKSPACE_RBAC_ENFORCEMENT_ENABLED", "true")
        monkeypatch.setenv("LEGACY_OWNER_BRIDGE_ENABLED", "false")
        owner_token = set_current_owner_id(users[0]); workspace_token = set_current_workspace_id(workspaces[0])
        try:
            async with sessions() as session:
                visible = list((await session.scalars(select(ProviderAccountModel))).all())
                assert [item.id for item in visible] == [accounts[0]]
                assert await session.get(ProviderAccountModel, accounts[1]) is None
        finally:
            reset_current_workspace_id(workspace_token); reset_current_owner_id(owner_token); await engine.dispose()

    if sys.platform == "win32":
        loop = asyncio.SelectorEventLoop()
        try: loop.run_until_complete(scenario())
        finally: loop.close()
    else:
        asyncio.run(scenario())


def test_postgresql_provider_secrets_snapshots_and_shared_circuit(monkeypatch):
    monkeypatch.setenv("POLICY_ROUTING_ENABLED", "true")
    monkeypatch.setenv("PROVIDER_FALLBACK_ENABLED", "false")

    async def scenario():
        engine = create_async_engine(_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        suffix = uuid4()
        async with sessions() as session:
            user = User(
                username=f"provider-state-pg-{suffix}",
                hashed_password="test",
            )
            session.add(user)
            await session.flush()
            workspace = WorkspaceModel(
                name=f"Provider State PG {suffix}",
                created_by=user.id,
            )
            session.add(workspace)
            await session.commit()

        registry = ProviderRegistry()
        adapter = FakeAdapter(
            "text.real-pg",
            CapabilityFamily.TEXT,
            result=TextAIResult(content="real pg", model="model-a"),
        )
        registry.register(adapter)
        keys = StaticKeys()
        plaintext = f"local-secret-{uuid4().hex}"
        async with sessions() as session:
            account = await add_account(
                session,
                workspace.id,
                adapter,
                f"Real PG {suffix}",
            )
            account_id = account.id
            workspace_id = workspace.id
            secret = await rotate_provider_secret(
                session,
                account_id=account_id,
                workspace_id=workspace_id,
                name="api_key",
                plaintext=plaintext,
                keys=keys,
            )
            await session.commit()
            assert plaintext not in secret.ciphertext
            assert plaintext not in repr(secret)
            assert (
                await resolve_provider_secret(
                    session,
                    account_id=account_id,
                    keys=keys,
                )
                == plaintext
            )
            with pytest.raises(SecretDecryptionError):
                await resolve_provider_secret(
                    session,
                    account_id=account_id,
                    keys=StaticKeys(value=b"z" * 32),
                )
            original_ciphertext = secret.ciphertext
            secret.ciphertext = (
                ("A" if original_ciphertext[0] != "A" else "B")
                + original_ciphertext[1:]
            )
            await session.commit()
            with pytest.raises(SecretDecryptionError):
                await resolve_provider_secret(
                    session,
                    account_id=account_id,
                    keys=keys,
                )
            secret.ciphertext = original_ciphertext
            await session.commit()

            result = await ProviderExecutor(registry=registry, keys=keys).execute(
                session,
                workspace_id=workspace_id,
                request=TextAIRequest(
                    messages=[TextMessage(role="user", content="safe local prompt")],
                    model="model-a",
                ),
                pinned_account_id=account_id,
            )
            assert result.content == "real pg"
            snapshot = await session.get(
                ProviderSnapshotModel,
                result.provider_snapshot_id,
            )
            assert snapshot is not None
            assert plaintext not in repr(snapshot)
            usage = await session.scalar(select(ProviderUsageModel).where(
                ProviderUsageModel.provider_snapshot_id == result.provider_snapshot_id,
            ))
            assert usage is not None and usage.status == "SUCCEEDED"
            assert usage.workspace_id == workspace_id and usage.provider_account_id == account_id
            snapshot.fallback_reason = "mutation"
            with pytest.raises(ValueError, match="immutable"):
                await session.commit()
            await session.rollback()

            for _ in range(3):
                await record_failure(
                    session,
                    account_id=account_id,
                    family=CapabilityFamily.TEXT,
                    model="model-a",
                )
            await session.commit()
        async with sessions() as observer:
            assert not await allow_call(
                observer,
                account_id=account_id,
                workspace_id=workspace_id,
                family=CapabilityFamily.TEXT,
                model="model-a",
            )
        async with sessions() as session:
            circuit = await session.scalar(
                select(ProviderCircuitModel).where(
                    ProviderCircuitModel.provider_account_id == account_id
                )
            )
            assert circuit is not None and circuit.state == CircuitState.OPEN
            circuit.opened_until = get_current_utc_datetime() - timedelta(seconds=1)
            await session.commit()
        async with sessions() as first_probe:
            assert await allow_call(
                first_probe,
                account_id=account_id,
                workspace_id=workspace_id,
                family=CapabilityFamily.TEXT,
                model="model-a",
            )
            await first_probe.commit()
        async with sessions() as second_probe:
            assert not await allow_call(
                second_probe,
                account_id=account_id,
                workspace_id=workspace_id,
                family=CapabilityFamily.TEXT,
                model="model-a",
            )
        async with sessions() as session:
            await record_success(
                session,
                account_id=account_id,
                family=CapabilityFamily.TEXT,
                model="model-a",
            )
            await session.commit()
            circuit = await session.scalar(
                select(ProviderCircuitModel).where(
                    ProviderCircuitModel.provider_account_id == account_id
                )
            )
            assert circuit is not None and circuit.state == CircuitState.CLOSED
            assert await delete_provider_secret(session, account_id=account_id) == 1
            await session.commit()
            assert (
                await session.scalar(
                    select(EncryptedProviderSecretModel).where(
                        EncryptedProviderSecretModel.provider_account_id == account_id
                    )
                )
                is None
            )
        await engine.dispose()

    if sys.platform == "win32":
        loop = asyncio.SelectorEventLoop()
        try:
            loop.run_until_complete(scenario())
        finally:
            loop.close()
    else:
        asyncio.run(scenario())
