"""Controlled HTTP and architecture acceptance for the Sprint 10 cutover."""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path

import pytest
from aiohttp import web
from sqlmodel import select

from modules.assets.domain.models import AssetState
from modules.assets.persistence.models import AssetModel
from modules.assets.providers.storage.registry import get_storage_provider
from modules.jobs.persistence.models import JobModel
from modules.providers.adapters.registry import PROVIDER_REGISTRY
from modules.providers.application.executor import ProviderExecutor
from modules.providers.application.legacy_facade import get_text_provider_client_config
from modules.providers.application.text_client import ProviderTextClientConfig, get_text_client
from modules.providers.domain.contracts import CapabilityFamily, ImageAIRequest, SearchRequest, TextAIRequest, TextMessage
from modules.providers.persistence.models import ProviderUsageModel
from modules.providers.security.secrets import rotate_provider_secret
from modules.providers.tests.test_providers import StaticKeys, add_account, database
from api.v1.auth.context import reset_current_workspace_id, set_current_workspace_id
from llmai.shared import UserMessage


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def test_official_adapters_execute_controlled_http_and_image_becomes_managed_asset(tmp_path, monkeypatch):
    monkeypatch.setenv("DISABLE_IMAGE_GENERATION", "false")
    monkeypatch.setenv("DISABLE_AI_IMAGE_GENERATION", "false")
    monkeypatch.setenv("POLICY_ROUTING_ENABLED", "true")
    monkeypatch.setenv("PROVIDER_FALLBACK_ENABLED", "false")
    monkeypatch.setenv("DURABLE_JOBS_ENABLED", "true")
    monkeypatch.setenv("OBJECT_STORAGE_WRITES_ENABLED", "true")
    monkeypatch.setenv("ASSET_LIBRARY_ENABLED", "true")
    monkeypatch.setenv("OBJECT_STORAGE_PROVIDER", "local")
    monkeypatch.setenv("OBJECT_STORAGE_LOCAL_ROOT", str(tmp_path / "objects"))
    get_storage_provider.cache_clear()

    async def scenario():
        async def text_response(request):
            payload = await request.json()
            return web.json_response({
                "id": "controlled-text",
                "model": payload["model"],
                "choices": [{"message": {"role": "assistant", "content": '{"title":"Controlled"}'}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 3},
            })

        async def image_response(request):
            await request.json()
            return web.json_response({"data": [{"b64_json": base64.b64encode(PNG_1X1).decode("ascii")}]})

        async def search_response(request):
            assert request.query.get("format") == "json"
            return web.json_response({"results": [
                {"title": "Controlled source", "url": "https://example.com/source#fragment", "content": "Safe result"},
                {"title": "Second source", "url": "https://example.org/two", "content": "Second"},
            ]})

        app = web.Application()
        app.router.add_post("/v1/chat/completions", text_response)
        app.router.add_post("/v1/images/generations", image_response)
        app.router.add_get("/search", search_response)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        origin = f"http://127.0.0.1:{port}"
        monkeypatch.setenv("OUTBOUND_HTTP_ALLOWLIST", origin)

        engine, sessions, _, workspace_id, _ = await database(tmp_path, "official-cutover.db")
        keys = StaticKeys()
        try:
            async with sessions() as session:
                text_adapter = PROVIDER_REGISTRY.get("text.custom")
                image_adapter = PROVIDER_REGISTRY.get("image.openai_compatible")
                search_adapter = PROVIDER_REGISTRY.get("search.searxng")
                text_account = await add_account(session, workspace_id, text_adapter, "Controlled text")
                text_account.safe_config = {"base_url": f"{origin}/v1"}
                image_account = await add_account(session, workspace_id, image_adapter, "Controlled image", model="controlled-image")
                image_account.safe_config = {"base_url": f"{origin}/v1", "model": "controlled-image"}
                search_account = await add_account(session, workspace_id, search_adapter, "Controlled search", model="default")
                search_account.safe_config = {"base_url": origin}
                await rotate_provider_secret(session, account_id=text_account.id, workspace_id=workspace_id, name="api_key", plaintext="controlled-text-secret", keys=keys)
                await rotate_provider_secret(session, account_id=image_account.id, workspace_id=workspace_id, name="api_key", plaintext="controlled-image-secret", keys=keys)
                await session.commit()
                account_ids = (text_account.id, image_account.id, search_account.id)

            executor = ProviderExecutor(keys=keys)
            async with sessions() as session:
                text = await executor.execute(
                    session, workspace_id=workspace_id,
                    request=TextAIRequest(messages=[TextMessage(role="user", content="Build a controlled title")], model="model-a"),
                    pinned_account_id=account_ids[0], operation="presentation.outline",
                )
                assert text.structured == {"title": "Controlled"}
                assert text.usage.input_tokens == 7 and text.usage.output_tokens == 3

            async with sessions() as session:
                image = await executor.execute(
                    session, workspace_id=workspace_id,
                    request=ImageAIRequest(prompt="Controlled image", model="controlled-image"),
                    pinned_account_id=account_ids[1], operation="image.presentation",
                )
                assert len(image.asset_ids) == 1
                asset = await session.get(AssetModel, image.asset_ids[0])
                assert asset is not None and asset.state == AssetState.QUARANTINED
                assert await get_storage_provider("local").head(asset.storage_key)
                scan = await session.scalar(select(JobModel).where(JobModel.operation == "asset.scan"))
                assert scan is not None and set(scan.payload) == {"asset_id"}
                assert "controlled-image-secret" not in repr(scan.payload)

            async with sessions() as session:
                search = await executor.execute(
                    session, workspace_id=workspace_id,
                    request=SearchRequest(query="Controlled sources", result_count=2),
                    pinned_account_id=account_ids[2], operation="search.presentation_outline",
                )
                assert len(search.items) == 2
                assert search.items[0].url == "https://example.com/source"
                events = list((await session.scalars(select(ProviderUsageModel).where(ProviderUsageModel.workspace_id == workspace_id))).all())
                assert {event.operation for event in events} == {"presentation.outline", "image.presentation", "search.presentation_outline"}
                assert all(event.provider_snapshot_id and event.status == "SUCCEEDED" for event in events)
        finally:
            await engine.dispose()
            await runner.cleanup()
            get_storage_provider.cache_clear()

    asyncio.run(scenario())


def test_controlled_image_and_search_failures_are_bounded_and_normalized(tmp_path, monkeypatch):
    monkeypatch.setenv("DISABLE_IMAGE_GENERATION", "false")
    monkeypatch.setenv("DISABLE_AI_IMAGE_GENERATION", "false")
    monkeypatch.setenv("POLICY_ROUTING_ENABLED", "true")
    monkeypatch.setenv("PROVIDER_FALLBACK_ENABLED", "false")

    async def scenario():
        async def image_response(request):
            mode = request.match_info["mode"]
            await request.json()
            if mode == "timeout":
                await asyncio.sleep(0.1)
            if mode == "error":
                return web.json_response({"error": "controlled"}, status=500)
            return web.json_response({"unexpected": []})

        async def search_response(request):
            mode = request.match_info["mode"]
            if mode == "timeout":
                await asyncio.sleep(0.1)
            if mode == "error":
                return web.json_response({"error": "controlled"}, status=500)
            if mode == "malformed":
                return web.Response(text="not-json", content_type="text/plain")
            return web.json_response({"results": [
                {"title": f"Result {index}", "url": f"https://example.com/{index}", "content": "controlled"}
                for index in range(45)
            ]})

        app = web.Application()
        app.router.add_post("/image/{mode}/v1/images/generations", image_response)
        app.router.add_get("/search/{mode}/search", search_response)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        origin = f"http://127.0.0.1:{port}"
        monkeypatch.setenv("OUTBOUND_HTTP_ALLOWLIST", origin)
        engine, sessions, _, workspace_id, _ = await database(tmp_path, "controlled-failures.db")
        keys = StaticKeys()
        try:
            accounts = {}
            async with sessions() as session:
                for family, modes in (("image", ("malformed", "timeout", "error")), ("search", ("excessive", "malformed", "timeout", "error"))):
                    adapter = PROVIDER_REGISTRY.get("image.openai_compatible" if family == "image" else "search.searxng")
                    for mode in modes:
                        account = await add_account(session, workspace_id, adapter, f"{family}-{mode}", model="controlled")
                        account.safe_config = {
                            "base_url": f"{origin}/{family}/{mode}/v1" if family == "image" else f"{origin}/search/{mode}",
                            **({"model": "controlled"} if family == "image" else {}),
                        }
                        if family == "image":
                            await rotate_provider_secret(session, account_id=account.id, workspace_id=workspace_id, name="api_key", plaintext="controlled", keys=keys)
                        accounts[(family, mode)] = account.id
                await session.commit()

            executor = ProviderExecutor(keys=keys)
            for mode, expected in (("malformed", "INVALID_RESPONSE"), ("timeout", "TIMEOUT"), ("error", "PROVIDER_UNAVAILABLE")):
                async with sessions() as session:
                    with pytest.raises(Exception) as failure:
                        await executor.execute(
                            session, workspace_id=workspace_id,
                            request=ImageAIRequest(prompt="controlled", model="controlled", timeout_seconds=0.01 if mode == "timeout" else 30),
                            pinned_account_id=accounts[("image", mode)],
                        )
                    assert failure.value.code.value == expected

            async with sessions() as session:
                bounded = await executor.execute(
                    session, workspace_id=workspace_id,
                    request=SearchRequest(query="controlled", result_count=3),
                    pinned_account_id=accounts[("search", "excessive")],
                )
                assert len(bounded.items) == 3
            for mode, expected in (("malformed", "INVALID_RESPONSE"), ("timeout", "TIMEOUT"), ("error", "PROVIDER_UNAVAILABLE")):
                async with sessions() as session:
                    with pytest.raises(Exception) as failure:
                        await executor.execute(
                            session, workspace_id=workspace_id,
                            request=SearchRequest(query="controlled", result_count=3, timeout_seconds=0.01 if mode == "timeout" else 5),
                            pinned_account_id=accounts[("search", mode)],
                        )
                    assert failure.value.code.value == expected
        finally:
            await engine.dispose()
            await runner.cleanup()

    asyncio.run(scenario())


def test_business_text_facade_prefers_registry_even_when_legacy_rollback_is_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("PROVIDER_REGISTRY_ENABLED", "true")
    monkeypatch.setenv("ENCRYPTED_PROVIDER_CONFIG_ENABLED", "true")
    monkeypatch.setenv("POLICY_ROUTING_ENABLED", "true")
    monkeypatch.setenv("LEGACY_PROVIDER_SWITCHES_ENABLED", "true")

    workspace_id = __import__("uuid").uuid4()
    observed = {}

    class SessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *_):
            return None

    async def execute(_executor, _session, **kwargs):
        observed.update(kwargs)
        from modules.providers.domain.contracts import TextAIResult, UsageUnits

        return TextAIResult(
            content="provider-platform", model="model-a",
            usage=UsageUnits(input_tokens=2, output_tokens=1),
        )

    import services.database as database_service
    import modules.providers.application.text_client as text_client_module

    monkeypatch.setattr(database_service, "async_session_maker", lambda: SessionContext())
    monkeypatch.setattr(text_client_module.ProviderExecutor, "execute", execute)
    config = get_text_provider_client_config(operation="presentation.generate")
    assert isinstance(config, ProviderTextClientConfig)
    client = get_text_client(config=config)
    token = set_current_workspace_id(workspace_id)
    try:
        result = client.generate(
            model="model-a",
            messages=[UserMessage(content="Use the authoritative path")],
        )
    finally:
        reset_current_workspace_id(token)
    assert result.content == "provider-platform"
    assert observed["workspace_id"] == workspace_id
    assert observed["operation"] == "presentation.generate"

    monkeypatch.setenv("PROVIDER_REGISTRY_ENABLED", "false")
    import utils.llm_config as legacy_llm_config

    sentinel = object()
    monkeypatch.setattr(legacy_llm_config, "get_llm_config", lambda **_: sentinel)
    legacy_config = get_text_provider_client_config()
    assert legacy_config is sentinel


def test_production_business_modules_cannot_bypass_provider_boundary():
    backend = Path(__file__).resolve().parents[3]
    python_files = [
        path for root in ("api", "services", "templates", "utils", "modules")
        for path in (backend / root).rglob("*.py")
        if "tests" not in path.parts and "__pycache__" not in path.parts
    ]
    direct_text_clients = []
    direct_image_implementations = []
    direct_search_implementations = []
    for path in python_files:
        relative = path.relative_to(backend).as_posix()
        source = path.read_text(encoding="utf-8")
        if "from llmai import get_client" in source and relative not in {
            "modules/providers/adapters/compatibility.py",
            "modules/providers/application/text_client.py",
        }:
            direct_text_clients.append(relative)
        if "services.image_generation_service import" in source and relative not in {
            "modules/providers/adapters/compatibility.py",
            "modules/providers/application/legacy_image_facade.py",
        }:
            direct_image_implementations.append(relative)
        if "utils.web_search import" in source and relative not in {
            "modules/providers/adapters/compatibility.py",
            "modules/providers/application/legacy_search_facade.py",
        }:
            direct_search_implementations.append(relative)
    assert direct_text_clients == []
    assert direct_image_implementations == []
    assert direct_search_implementations == []
