import asyncio
import base64
import json
from datetime import timedelta
from uuid import uuid4

import pytest
from aiohttp import ClientSession, web
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select

from models.sql.provider_settings import ProviderSettings
from models.sql.user import User
from modules.jobs.application.submit import JobSubmission, assert_secret_free_payload, submit_job
from modules.jobs.domain.models import JobStatus, QueueClass
from modules.jobs.outbox import dispatch_outbox_batch
from modules.jobs.persistence.models import ConsumerInboxModel, DeadLetterModel, JobAttemptModel, JobEventModel, JobModel, OutboxMessageModel
from modules.jobs.workers.registry import JobRegistry
from modules.jobs.workers.runtime import JobWorker
from modules.assets.persistence.models import AssetModel, AssetReferenceModel, ObjectVersionModel, UploadSessionModel
from modules.providers.adapters.registry import PROVIDER_REGISTRY, CompatibilityAdapter, ProviderExecutionError, ProviderRegistry
from modules.providers.application.circuit import allow_call, record_failure, record_success
from modules.providers.application.configuration import create_provider_account, validate_safe_config
from modules.providers.application.executor import ProviderExecutor
from modules.providers.application.legacy_migration import migrate_legacy_provider_settings
from modules.providers.domain.contracts import (
    CapabilityFamily, CircuitState, ImageAIAdapterResult, ImageAIRequest, ImageAIResult, ImageProviderOutput, ProviderHealthStatus,
    RegionPolicyStatus, SearchItem, SearchRequest, SearchResult, TextAIRequest, TextAIResult,
    TextMessage, UsageUnits,
)
from modules.providers.domain.routing import plan_route
from modules.providers.persistence.models import (
    EncryptedProviderSecretModel, ProviderAccountModel, ProviderCapabilityModel,
    ProviderCircuitModel, ProviderHealthModel, ProviderSnapshotModel, RoutingPolicyModel,
    ProviderUsageModel,
)
from modules.providers.security.secrets import SecretDecryptionError, delete_provider_secret, resolve_provider_secret, rotate_provider_secret
from modules.providers.workers.handlers import register_provider_handlers
from modules.workspaces.domain.models import MembershipStatus, Role
from modules.workspaces.persistence.models import AuditEventModel, MembershipModel, ServiceAccountModel, WorkspaceModel
from utils.api_errors import StableAPIError
from utils.datetime_utils import get_current_utc_datetime


TABLES = (
    User.__table__, WorkspaceModel.__table__, MembershipModel.__table__, ServiceAccountModel.__table__, AuditEventModel.__table__,
    ProviderSettings.__table__, JobModel.__table__, JobAttemptModel.__table__, OutboxMessageModel.__table__, ConsumerInboxModel.__table__,
    DeadLetterModel.__table__, JobEventModel.__table__, ProviderAccountModel.__table__, EncryptedProviderSecretModel.__table__,
    ProviderCapabilityModel.__table__, ProviderHealthModel.__table__, RoutingPolicyModel.__table__, ProviderSnapshotModel.__table__, ProviderCircuitModel.__table__, ProviderUsageModel.__table__,
    AssetModel.__table__, ObjectVersionModel.__table__, UploadSessionModel.__table__, AssetReferenceModel.__table__,
)


class StaticKeys:
    def __init__(self, version="test-v1", value=b"k" * 32): self.version, self.value = version, value
    def active_key(self): return self.version, self.value
    def key(self, version):
        if version != self.version: raise SecretDecryptionError("missing key")
        return self.value


class FakeAdapter:
    def __init__(self, adapter_id, family, *, result=None, error=None, delay=0):
        self.adapter_id = adapter_id; self.family = family; self.models = ("model-a",)
        self.safe_metadata = {"secretRequired": False, "test": True}
        self.result = result; self.error = error; self.delay = delay; self.calls = 0
    async def execute(self, request, *, secret, safe_config):
        self.calls += 1
        if self.delay: await asyncio.sleep(self.delay)
        if self.error: raise self.error
        return self.result
    async def connection_test(self, *, secret, safe_config, timeout_seconds): return ProviderHealthStatus.HEALTHY


class LocalHTTPTextAdapter:
    adapter_id = "text.local-http-test"
    family = CapabilityFamily.TEXT
    models = ("model-a",)
    safe_metadata = {"secretRequired": False, "test": True}

    async def execute(self, request, *, secret, safe_config):
        del secret
        try:
            async with ClientSession() as client:
                async with client.post(
                    safe_config["endpoint"],
                    json=request.model_dump(mode="json"),
                ) as response:
                    if response.status == 429:
                        raise ProviderExecutionError(
                            "RATE_LIMIT", "Controlled rate limit", retryable=True
                        )
                    if response.status >= 500:
                        raise ProviderExecutionError(
                            "SERVER_ERROR", "Controlled server failure", retryable=True
                        )
                    raw = await response.read()
            return TextAIResult.model_validate_json(raw)
        except ProviderExecutionError:
            raise
        except (ValidationError, ValueError) as exc:
            raise ProviderExecutionError(
                "INVALID_RESPONSE",
                "Controlled provider returned malformed data",
                retryable=True,
            ) from exc

    async def connection_test(self, *, secret, safe_config, timeout_seconds):
        del secret, safe_config, timeout_seconds
        return ProviderHealthStatus.HEALTHY


class FakeTransport:
    def __init__(self): self.deliveries = []
    async def publish(self, delivery): self.deliveries.append(delivery)
    async def consume(self, _queue_class, timeout=5): return self.deliveries.pop(0) if self.deliveries else None
    async def health(self): return True
    async def close(self): return None


async def database(tmp_path, name="providers.db"):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / name}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync: SQLModel.metadata.create_all(sync, tables=TABLES))
    async with sessions() as session:
        user = User(username=f"provider-{name}", hashed_password="test")
        session.add(user); await session.flush()
        workspace = WorkspaceModel(name="Providers", created_by=user.id)
        other = WorkspaceModel(name="Other", created_by=user.id)
        session.add_all([workspace, other]); await session.flush()
        session.add_all([
            MembershipModel(workspace_id=workspace.id, user_id=user.id, role=Role.OWNER, status=MembershipStatus.ACTIVE),
            MembershipModel(workspace_id=other.id, user_id=user.id, role=Role.OWNER, status=MembershipStatus.ACTIVE),
        ])
        await session.commit()
    return engine, sessions, user.id, workspace.id, other.id


async def add_account(session, workspace_id, adapter, name, model="model-a", region=RegionPolicyStatus.ALLOWED):
    account = ProviderAccountModel(workspace_id=workspace_id, adapter_id=adapter.adapter_id, name=name, default_model=model, region_policy_status=region)
    session.add(account); await session.flush()
    session.add_all([
        ProviderCapabilityModel(provider_account_id=account.id, workspace_id=workspace_id, family=adapter.family, model=model),
        ProviderHealthModel(provider_account_id=account.id, workspace_id=workspace_id),
    ])
    await session.flush()
    return account


def test_normalized_text_image_and_search_contracts_and_static_adapter_wrapper():
    text = TextAIRequest(messages=[TextMessage(role="user", content="hello")], model="model-a")
    image = ImageAIRequest(prompt="safe illustration", reference_asset_ids=[uuid4()])
    search = SearchRequest(query="public sources")
    assert text.messages[0].role == "user" and image.count == 1 and search.safe_search
    assert TextAIResult(content="ok", model="model-a", usage=UsageUnits(input_tokens=1)).content == "ok"
    assert ImageAIResult(asset_ids=[uuid4()], model="image-a").asset_ids
    assert SearchResult(items=[SearchItem(title="Source", url="https://example.com")]).usage.search_calls == 1

    async def scenario():
        adapter = CompatibilityAdapter("text.test", CapabilityFamily.TEXT, legacy_id="test", secret_required=True)
        assert await adapter.connection_test(secret="credential", safe_config={}, timeout_seconds=1) == ProviderHealthStatus.UNKNOWN
        with pytest.raises(ProviderExecutionError) as missing:
            await adapter.execute(text, secret=None, safe_config={})
        assert missing.value.code == "CREDENTIALS_MISSING"
        registered = PROVIDER_REGISTRY.list()
        assert registered and {item.family for item in registered} == set(CapabilityFamily)
        for current in registered:
            if current.adapter_id in {"search.auto", "search.native"}:
                request = search
                with pytest.raises(ProviderExecutionError) as controlled:
                    await current.execute(request, secret=None, safe_config={})
                assert controlled.value.code == "LEGACY_BRIDGE_REQUIRED"
                assert current.safe_metadata["liveConnectionTest"] is False
            else:
                assert current.safe_metadata["liveConnectionTest"] is True
                assert current._bridge is not None
    asyncio.run(scenario())


def test_account_edit_synchronizes_model_capabilities(tmp_path, monkeypatch):
    async def scenario():
        from types import SimpleNamespace

        from modules.providers.api import router as provider_api

        engine, sessions, user_id, workspace_id, _ = await database(
            tmp_path, "account-edit-capabilities.db"
        )
        try:
            async with sessions() as session:
                account = await add_account(
                    session,
                    workspace_id,
                    PROVIDER_REGISTRY.get("text.custom"),
                    "Editable",
                    model="model-a",
                )
                await session.commit()
                account_id = account.id

            async def authorized_account(session, _request, _account_id, _permission, *, lock=False):
                del lock
                account = await session.get(ProviderAccountModel, _account_id)
                return account, SimpleNamespace(user_id=user_id)

            monkeypatch.setattr(provider_api, "_account", authorized_account)
            request = SimpleNamespace()
            async with sessions() as session:
                updated = await provider_api.update_account(
                    account_id,
                    provider_api.AccountUpdate(
                        defaultModel="model-b",
                        capabilityModels=["model-b", "model-c", "model-b"],
                    ),
                    request,
                    session,
                )
                assert updated["defaultModel"] == "model-b"
                states = {
                    (item.model, item.enabled)
                    for item in (
                        await session.scalars(
                            select(ProviderCapabilityModel).where(
                                ProviderCapabilityModel.provider_account_id == account_id
                            )
                        )
                    ).all()
                }
                assert states == {
                    ("model-a", False),
                    ("model-b", True),
                    ("model-c", True),
                }

            async with sessions() as session:
                with pytest.raises(StableAPIError) as invalid:
                    await provider_api.update_account(
                        account_id,
                        provider_api.AccountUpdate(
                            defaultModel="missing",
                            capabilityModels=["model-b"],
                        ),
                        request,
                        session,
                    )
                assert invalid.value.code == "PROVIDER_DEFAULT_MODEL_INVALID"
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_secret_encryption_wrong_key_rotation_deletion_and_redaction(tmp_path):
    async def scenario():
        engine, sessions, user_id, workspace_id, _ = await database(tmp_path, "secrets.db")
        adapter = FakeAdapter("text.fake", CapabilityFamily.TEXT)
        async with sessions() as session:
            account = await add_account(session, workspace_id, adapter, "Secret")
            first = await rotate_provider_secret(session, account_id=account.id, workspace_id=workspace_id, name="api_key", plaintext="first-secret", keys=StaticKeys())
            await session.commit()
            assert "first-secret" not in repr(first)
            assert "ciphertext" not in first.model_dump()
            assert await resolve_provider_secret(session, account_id=account.id, keys=StaticKeys()) == "first-secret"
            with pytest.raises(SecretDecryptionError):
                await resolve_provider_secret(session, account_id=account.id, keys=StaticKeys(value=b"z" * 32))
            second = await rotate_provider_secret(session, account_id=account.id, workspace_id=workspace_id, name="api_key", plaintext="second-secret", keys=StaticKeys())
            await session.commit()
            assert second.version == 2 and await resolve_provider_secret(session, account_id=account.id, keys=StaticKeys()) == "second-secret"
            assert await delete_provider_secret(session, account_id=account.id) == 2
            await session.commit()
            assert await resolve_provider_secret(session, account_id=account.id, keys=StaticKeys()) is None
        await engine.dispose()
    asyncio.run(scenario())


def test_deterministic_routing_fallback_pinning_region_emergency_and_workspace_isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("POLICY_ROUTING_ENABLED", "true")
    monkeypatch.setenv("PROVIDER_FALLBACK_ENABLED", "true")
    async def scenario():
        engine, sessions, _, workspace_id, other_id = await database(tmp_path, "routing.db")
        registry = ProviderRegistry()
        first_adapter = FakeAdapter("text.first", CapabilityFamily.TEXT); second_adapter = FakeAdapter("text.second", CapabilityFamily.TEXT)
        registry.register(first_adapter); registry.register(second_adapter)
        async with sessions() as session:
            first = await add_account(session, workspace_id, first_adapter, "First")
            second = await add_account(session, workspace_id, second_adapter, "Second")
            await add_account(session, other_id, first_adapter, "Other")
            session.add(RoutingPolicyModel(workspace_id=workspace_id, family=CapabilityFamily.TEXT, priority_account_ids=[str(second.id), str(first.id), "invalid"], allow_fallback=True, max_fallbacks=1))
            await session.commit()
            planned = await plan_route(session, workspace_id=workspace_id, family=CapabilityFamily.TEXT, model="model-a", registry=registry)
            assert [item.account.id for item in planned.candidates] == [second.id, first.id]
            assert all(item.account.workspace_id == workspace_id for item in planned.candidates)
            monkeypatch.setenv("DISABLED_PROVIDER_ADAPTERS", second.adapter_id)
            disabled = await plan_route(session, workspace_id=workspace_id, family=CapabilityFamily.TEXT, registry=registry)
            assert disabled.candidates[0].account.id == first.id and disabled.exclusions[str(second.id)] == "ADAPTER_EMERGENCY_DISABLED"
            monkeypatch.delenv("DISABLED_PROVIDER_ADAPTERS")
            pinned = await plan_route(session, workspace_id=workspace_id, family=CapabilityFamily.TEXT, pinned_account_id=first.id, registry=registry)
            assert [item.account.id for item in pinned.candidates] == [first.id]
            second.emergency_disabled = True; await session.commit()
            planned = await plan_route(session, workspace_id=workspace_id, family=CapabilityFamily.TEXT, registry=registry)
            assert planned.candidates[0].account.id == first.id and planned.exclusions[str(second.id)] == "EMERGENCY_DISABLED"
            first.region_policy_status = RegionPolicyStatus.UNKNOWN; await session.commit()
            with pytest.raises(StableAPIError) as unavailable:
                await plan_route(session, workspace_id=workspace_id, family=CapabilityFamily.TEXT, pinned_account_id=first.id, registry=registry)
            assert unavailable.value.code == "PINNED_PROVIDER_UNAVAILABLE"
        await engine.dispose()
    asyncio.run(scenario())


def test_executor_timeout_budget_bounded_fallback_snapshot_and_circuit(tmp_path, monkeypatch):
    monkeypatch.setenv("POLICY_ROUTING_ENABLED", "true")
    monkeypatch.setenv("PROVIDER_FALLBACK_ENABLED", "true")
    async def scenario():
        engine, sessions, _, workspace_id, _ = await database(tmp_path, "executor.db")
        registry = ProviderRegistry()
        failing = FakeAdapter("text.failing", CapabilityFamily.TEXT, error=ProviderExecutionError("RATE_LIMIT", "rate limited", retryable=True))
        succeeding = FakeAdapter("text.succeeding", CapabilityFamily.TEXT, result=TextAIResult(content="done", model="model-a", usage=UsageUnits(input_tokens=10, output_tokens=20)))
        registry.register(failing); registry.register(succeeding)
        async with sessions() as session:
            first = await add_account(session, workspace_id, failing, "Failing")
            second = await add_account(session, workspace_id, succeeding, "Succeeding")
            second.safe_config = {
                "price_input_per_million": 1.0,
                "price_output_per_million": 2.0,
                "currency": "USD",
                "pricing_version": "controlled-v1",
            }
            session.add(RoutingPolicyModel(workspace_id=workspace_id, family=CapabilityFamily.TEXT, priority_account_ids=[str(first.id), str(second.id)], allow_fallback=True, max_fallbacks=1))
            await session.commit()
            request = TextAIRequest(messages=[TextMessage(role="user", content="content must not enter snapshot")], model="model-a", timeout_seconds=1)
            result = await ProviderExecutor(registry=registry, keys=StaticKeys()).execute(session, workspace_id=workspace_id, request=request)
            assert result.content == "done" and result.provider_snapshot_id is not None
            assert result.cost.amount == pytest.approx(0.00005)
            assert failing.calls == 1 and succeeding.calls == 1
            snapshots = list((await session.scalars(select(ProviderSnapshotModel).order_by(ProviderSnapshotModel.created_at))).all())
            assert len(snapshots) == 2 and snapshots[1].fallback_reason == "RATE_LIMIT"
            assert "content must not enter snapshot" not in repr(snapshots)
            usage_events = list((await session.scalars(select(ProviderUsageModel).order_by(ProviderUsageModel.created_at))).all())
            assert [item.status for item in usage_events] == ["FAILED", "SUCCEEDED"]
            assert usage_events[1].input_tokens == 10 and usage_events[1].output_tokens == 20
            assert usage_events[1].estimated_cost == pytest.approx(0.00005)
            assert "content must not enter snapshot" not in repr(usage_events)
            circuit = await session.scalar(select(ProviderCircuitModel).where(ProviderCircuitModel.provider_account_id == first.id))
            assert circuit.failure_count == 1
            snapshots[0].fallback_reason = "mutation"
            with pytest.raises(ValueError, match="immutable"):
                await session.commit()
            await session.rollback()

        timeout_registry = ProviderRegistry()
        slow = FakeAdapter("text.slow", CapabilityFamily.TEXT, result=TextAIResult(content="late", model="model-a"), delay=.05)
        timeout_registry.register(slow)
        async with sessions() as session:
            account = await add_account(session, workspace_id, slow, "Slow")
            await session.commit()
            request = TextAIRequest(messages=[TextMessage(role="user", content="x")], model="model-a", timeout_seconds=.01)
            with pytest.raises(Exception) as timeout:
                await ProviderExecutor(registry=timeout_registry, keys=StaticKeys()).execute(session, workspace_id=workspace_id, request=request, pinned_account_id=account.id)
            assert getattr(timeout.value, "code", None).value == "TIMEOUT"
        await engine.dispose()
    asyncio.run(scenario())


def test_provider_executor_with_controlled_local_http_failures(tmp_path, monkeypatch):
    monkeypatch.setenv("POLICY_ROUTING_ENABLED", "true")
    monkeypatch.setenv("PROVIDER_FALLBACK_ENABLED", "false")
    monkeypatch.setenv("PROVIDER_MAX_RESPONSE_BYTES", "1024")

    async def scenario():
        async def respond(request):
            mode = request.match_info["mode"]
            await request.json()
            if mode == "timeout":
                await asyncio.sleep(0.1)
            if mode == "reset":
                if request.transport is not None:
                    request.transport.abort()
                return web.Response()
            if mode == "rate":
                return web.json_response({"error": "rate"}, status=429)
            if mode == "server":
                return web.json_response({"error": "server"}, status=500)
            if mode == "malformed":
                return web.Response(text="not-json", content_type="text/plain")
            content = "x" * 2048 if mode == "oversized" else "ok"
            return web.json_response(
                {
                    "content": content,
                    "structured": {"slides": 3},
                    "model": "model-a",
                }
            )

        app = web.Application(client_max_size=64 * 1024)
        app.router.add_post("/{mode}", respond)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        sockets = site._server.sockets
        port = sockets[0].getsockname()[1]

        engine, sessions, _, workspace_id, _ = await database(
            tmp_path, "local-http-provider.db"
        )
        registry = ProviderRegistry()
        adapter = LocalHTTPTextAdapter()
        registry.register(adapter)
        executor = ProviderExecutor(registry=registry, keys=StaticKeys())
        request = TextAIRequest(
            messages=[TextMessage(role="user", content="controlled request")],
            model="model-a",
            timeout_seconds=1,
        )
        try:
            accounts = {}
            async with sessions() as session:
                for mode in (
                    "success",
                    "rate",
                    "malformed",
                    "server",
                    "oversized",
                    "timeout",
                    "reset",
                ):
                    account = await add_account(
                        session,
                        workspace_id,
                        adapter,
                        f"Local HTTP {mode}",
                    )
                    account.safe_config = {
                        "endpoint": f"http://127.0.0.1:{port}/{mode}"
                    }
                    accounts[mode] = account.id
                await session.commit()

            async with sessions() as session:
                result = await executor.execute(
                    session,
                    workspace_id=workspace_id,
                    request=request,
                    pinned_account_id=accounts["success"],
                )
                assert result.content == "ok"
                assert result.structured == {"slides": 3}

            expected = {
                "rate": "RATE_LIMIT",
                "malformed": "INVALID_RESPONSE",
                "server": "PROVIDER_UNAVAILABLE",
                "oversized": "INVALID_RESPONSE",
                "timeout": "TIMEOUT",
                "reset": "PROVIDER_UNAVAILABLE",
            }
            for mode, code in expected.items():
                current_request = request.model_copy(
                    update={"timeout_seconds": 0.01 if mode == "timeout" else 1}
                )
                async with sessions() as session:
                    with pytest.raises(Exception) as failure:
                        await executor.execute(
                            session,
                            workspace_id=workspace_id,
                            request=current_request,
                            pinned_account_id=accounts[mode],
                        )
                    assert failure.value.code.value == code
        finally:
            await engine.dispose()
            await runner.cleanup()

    asyncio.run(scenario())


def test_provider_executor_normalizes_image_and_search_results(tmp_path, monkeypatch):
    monkeypatch.setenv("POLICY_ROUTING_ENABLED", "true")
    monkeypatch.setenv("PROVIDER_FALLBACK_ENABLED", "false")
    monkeypatch.setenv("PROVIDER_MAX_RESPONSE_BYTES", "1024")

    async def scenario():
        engine, sessions, _, workspace_id, _ = await database(
            tmp_path, "image-search-executor.db"
        )
        image_id = uuid4()
        registry = ProviderRegistry()
        image = FakeAdapter(
            "image.controlled",
            CapabilityFamily.IMAGE,
            result=ImageAIResult(
                asset_ids=[image_id],
                model="model-a",
                usage=UsageUnits(images=1),
            ),
        )
        search = FakeAdapter(
            "search.controlled",
            CapabilityFamily.SEARCH,
            result=SearchResult(
                items=[SearchItem(
                    title="Controlled result",
                    url="https://example.com/source",
                    snippet="Normalized search output",
                )]
            ),
        )
        oversized = FakeAdapter(
            "search.oversized",
            CapabilityFamily.SEARCH,
            result=SearchResult(items=[SearchItem(
                title="Oversized",
                url="https://example.com/large",
                snippet="x" * 2048,
            )]),
        )
        wrong_family = FakeAdapter(
            "image.wrong-family",
            CapabilityFamily.IMAGE,
            result=SearchResult(items=[]),
        )
        for adapter in (image, search, oversized, wrong_family):
            registry.register(adapter)
        async with sessions() as session:
            accounts = {}
            for adapter in (image, search, oversized, wrong_family):
                account = await add_account(
                    session, workspace_id, adapter, adapter.adapter_id
                )
                accounts[adapter.adapter_id] = account.id
            await session.commit()

        executor = ProviderExecutor(registry=registry, keys=StaticKeys())
        async with sessions() as session:
            image_result = await executor.execute(
                session,
                workspace_id=workspace_id,
                request=ImageAIRequest(prompt="Controlled illustration", model="model-a"),
                pinned_account_id=accounts[image.adapter_id],
            )
            assert image_result.asset_ids == [image_id]
            assert image_result.usage.images == 1
        async with sessions() as session:
            search_result = await executor.execute(
                session,
                workspace_id=workspace_id,
                request=SearchRequest(query="controlled sources"),
                pinned_account_id=accounts[search.adapter_id],
            )
            assert search_result.items[0].url == "https://example.com/source"
            assert search_result.usage.search_calls == 1

        for adapter_id, request in (
            (
                oversized.adapter_id,
                SearchRequest(query="oversized controlled response"),
            ),
            (
                wrong_family.adapter_id,
                ImageAIRequest(prompt="wrong normalized family", model="model-a"),
            ),
        ):
            async with sessions() as session:
                with pytest.raises(Exception) as invalid:
                    await executor.execute(
                        session,
                        workspace_id=workspace_id,
                        request=request,
                        pinned_account_id=accounts[adapter_id],
                    )
                assert invalid.value.code.value == "INVALID_RESPONSE"
        await engine.dispose()

    asyncio.run(scenario())


def test_shared_circuit_opens_half_opens_and_recovers(tmp_path):
    async def scenario():
        engine, sessions, _, workspace_id, _ = await database(tmp_path, "circuit.db")
        adapter = FakeAdapter("text.circuit", CapabilityFamily.TEXT)
        async with sessions() as session:
            account = await add_account(session, workspace_id, adapter, "Circuit")
            assert await allow_call(session, account_id=account.id, workspace_id=workspace_id, family=CapabilityFamily.TEXT, model="model-a")
            for _ in range(3): await record_failure(session, account_id=account.id, family=CapabilityFamily.TEXT, model="model-a")
            await session.commit()
            assert not await allow_call(session, account_id=account.id, workspace_id=workspace_id, family=CapabilityFamily.TEXT, model="model-a")
            row = await session.scalar(select(ProviderCircuitModel).where(ProviderCircuitModel.provider_account_id == account.id))
            row.opened_until = get_current_utc_datetime() - timedelta(seconds=1); await session.commit()
            assert await allow_call(session, account_id=account.id, workspace_id=workspace_id, family=CapabilityFamily.TEXT, model="model-a")
            assert not await allow_call(session, account_id=account.id, workspace_id=workspace_id, family=CapabilityFamily.TEXT, model="model-a")
            await record_failure(session, account_id=account.id, family=CapabilityFamily.TEXT, model="model-a")
            await session.commit()
            row = await session.scalar(select(ProviderCircuitModel).where(ProviderCircuitModel.provider_account_id == account.id))
            assert row.state == CircuitState.OPEN
            row.opened_until = get_current_utc_datetime() - timedelta(seconds=1); await session.commit()
            assert await allow_call(session, account_id=account.id, workspace_id=workspace_id, family=CapabilityFamily.TEXT, model="model-a")
            await record_success(session, account_id=account.id, family=CapabilityFamily.TEXT, model="model-a"); await session.commit()
            row = await session.scalar(select(ProviderCircuitModel).where(ProviderCircuitModel.provider_account_id == account.id))
            assert row.state == CircuitState.CLOSED and row.failure_count == 0
        await engine.dispose()
    asyncio.run(scenario())


def test_ssrf_custom_endpoint_and_secret_free_durable_payload(tmp_path):
    async def scenario():
        with pytest.raises(StableAPIError) as blocked:
            await validate_safe_config({"base_url": "http://127.0.0.1:8080"})
        assert blocked.value.code == "PROVIDER_ENDPOINT_BLOCKED"
        with pytest.raises(StableAPIError) as secret:
            await validate_safe_config({"api_key": "plaintext"})
        assert secret.value.code == "PROVIDER_SECRET_IN_CONFIG"
        assert_secret_free_payload({"provider_account_id": str(uuid4())})
        with pytest.raises(StableAPIError): assert_secret_free_payload({"provider_account_id": str(uuid4()), "api_key": "forbidden"})
        engine, sessions, user_id, workspace_id, _ = await database(tmp_path, "job-payload.db")
        async with sessions() as session:
            job, _ = await submit_job(session, JobSubmission(operation="provider.connection_test", queue_class=QueueClass.MAINTENANCE, workspace_id=workspace_id, actor_id=user_id, actor_service_account_id=None, idempotency_scope="provider:test", idempotency_key="one", payload={"provider_account_id": str(uuid4())}, max_attempts=2))
            await session.commit()
            assert set(job.payload) == {"provider_account_id"}
        await engine.dispose()
    asyncio.run(scenario())


def test_durable_connection_test_updates_health_without_secret_result(tmp_path, monkeypatch):
    async def scenario():
        engine, sessions, user_id, workspace_id, _ = await database(tmp_path, "connection.db")
        registry = ProviderRegistry(); adapter = FakeAdapter("text.connection", CapabilityFamily.TEXT); registry.register(adapter)
        import modules.providers.workers.handlers as handlers
        monkeypatch.setattr(handlers, "PROVIDER_REGISTRY", registry)
        async with sessions() as session:
            account = await add_account(session, workspace_id, adapter, "Connection")
            job, _ = await submit_job(session, JobSubmission(operation="provider.connection_test", queue_class=QueueClass.MAINTENANCE, workspace_id=workspace_id, actor_id=user_id, actor_service_account_id=None, idempotency_scope="provider:connection", idempotency_key="one", payload={"provider_account_id": str(account.id)}, max_attempts=2))
            await session.commit()
        transport = FakeTransport(); registry_jobs = JobRegistry(); register_provider_handlers(registry_jobs)
        async with sessions() as session: await dispatch_outbox_batch(session, transport)
        worker = JobWorker(sessions, transport, registry=registry_jobs, worker_id="provider-test", lease_seconds=10)
        processed = await worker.process_delivery(transport.deliveries[0])
        if not processed:
            async with sessions() as session:
                failed = await session.get(JobModel, job.id)
                pytest.fail(f"connection job did not complete: {failed.status.value} {failed.safe_error_code} {failed.safe_error_message}")
        async with sessions() as session:
            current = await session.get(JobModel, job.id)
            health = await session.scalar(select(ProviderHealthModel).where(ProviderHealthModel.provider_account_id == account.id))
            assert current.status == JobStatus.SUCCEEDED and health.status == ProviderHealthStatus.HEALTHY
            assert "secret" not in str(current.result).lower()
        await engine.dispose()
    asyncio.run(scenario())


def test_legacy_provider_mapping_is_dry_run_first_verified_and_preserves_original(tmp_path):
    async def scenario():
        engine, sessions, user_id, workspace_id, _ = await database(tmp_path, "legacy.db")
        async with sessions() as session:
            original = {"LLM": "openai", "OPENAI_MODEL": "gpt-test", "OPENAI_API_KEY": "legacy-secret"}
            session.add(ProviderSettings(id=1, config=original)); await session.commit()
            dry = await migrate_legacy_provider_settings(session, workspace_id=workspace_id, actor_id=user_id, apply=False, keys=StaticKeys())
            selected = next(item for item in dry if item.adapter_id == "text.openai")
            assert selected.has_secret and selected.account_id is None and selected.status == "READY"
            assert {
                item.adapter_id for item in dry if item.status == "ROLLBACK_ONLY"
            } == {"image.dall-e-3", "image.gpt-image-1.5"}
            assert not list((await session.scalars(select(ProviderAccountModel))).all())
            applied = await migrate_legacy_provider_settings(session, workspace_id=workspace_id, actor_id=user_id, apply=True, keys=StaticKeys())
            selected = next(item for item in applied if item.adapter_id == "text.openai")
            assert selected.status == "VERIFIED" and selected.account_id
            assert await resolve_provider_secret(session, account_id=selected.account_id, keys=StaticKeys()) == "legacy-secret"
            rerun = await migrate_legacy_provider_settings(session, workspace_id=workspace_id, actor_id=user_id, apply=True, keys=StaticKeys())
            assert next(item for item in rerun if item.adapter_id == "text.openai").account_id == selected.account_id
            legacy = await session.get(ProviderSettings, 1)
            assert legacy.config == original
        await engine.dispose()
    asyncio.run(scenario())


def test_legacy_multi_value_credentials_are_one_encrypted_envelope(tmp_path):
    async def scenario():
        engine, sessions, user_id, workspace_id, _ = await database(tmp_path, "legacy-multi.db")
        try:
            original = {
                "LLM": "bedrock",
                "BEDROCK_MODEL": "controlled-bedrock",
                "BEDROCK_REGION": "us-test-1",
                "BEDROCK_AWS_ACCESS_KEY_ID": "access-id",
                "BEDROCK_AWS_SECRET_ACCESS_KEY": "secret-value",
                "BEDROCK_AWS_SESSION_TOKEN": "session-value",
                "CODEX_ACCESS_TOKEN": "unselected-codex-token",
            }
            async with sessions() as session:
                session.add(ProviderSettings(id=1, config=original))
                await session.commit()
                dry = await migrate_legacy_provider_settings(
                    session, workspace_id=workspace_id, actor_id=user_id,
                    apply=False, keys=StaticKeys(),
                )
                bedrock = next(item for item in dry if item.adapter_id == "text.bedrock")
                codex = next(item for item in dry if item.adapter_id == "text.codex")
                assert bedrock.status == "READY" and bedrock.has_secret
                assert bedrock.safe_config == {"region": "us-test-1"}
                assert codex.status == "ROLLBACK_ONLY" and codex.has_secret
                applied = await migrate_legacy_provider_settings(
                    session, workspace_id=workspace_id, actor_id=user_id,
                    apply=True, keys=StaticKeys(),
                )
                account_id = next(item for item in applied if item.adapter_id == "text.bedrock").account_id
                envelope = json.loads(await resolve_provider_secret(
                    session, account_id=account_id, keys=StaticKeys(),
                ))
                assert envelope == {
                    "access_key_id": "access-id",
                    "secret_access_key": "secret-value",
                    "session_token": "session-value",
                }
                assert (await session.get(ProviderSettings, 1)).config == original
        finally:
            await engine.dispose()

    asyncio.run(scenario())
