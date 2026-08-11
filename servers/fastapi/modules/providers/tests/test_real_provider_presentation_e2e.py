"""Real-infrastructure cross-sprint acceptance for provider-backed generation.

The test uses PostgreSQL, Redis Streams, MinIO, the production durable
``presentation.generate`` handler, and the official HTTP compatibility
adapters.  Only non-provider side effects (export and webhooks) are replaced
with deterministic local test doubles.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import BackgroundTasks
from redis.asyncio import Redis
from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select

from api.v1.auth.context import (
    reset_current_owner_id,
    reset_current_workspace_id,
    set_current_owner_id,
    set_current_workspace_id,
)
from api.v1.ppt.endpoints import presentation as presentation_endpoint
from enums.async_task_status import AsyncTaskStatus
from models.generate_presentation_request import GeneratePresentationRequest
from models.presentation_and_path import PresentationAndPath
from models.sql.async_task import AsyncTaskModel
from models.sql.presentation import PresentationModel
from models.sql.presentation_document import PresentationDocumentModel
from models.sql.presentation_revision import PresentationRevisionModel
from models.sql.slide import SlideModel
from models.sql.user import User
from modules.assets.domain.models import AssetState
from modules.assets.persistence.models import AssetModel
from modules.assets.providers.storage.registry import get_storage_provider
from modules.assets.workers.handlers import register_asset_handlers
from modules.jobs.domain.models import JobStatus, QueueClass
from modules.jobs.outbox import RedisQueueTransport, dispatch_outbox_batch
from modules.jobs.persistence.models import JobModel, OutboxMessageModel
from modules.jobs.workers.handlers.core import register_core_handlers
from modules.jobs.workers.registry import JobRegistry
from modules.jobs.workers.runtime import JobWorker
from modules.providers.adapters.registry import PROVIDER_REGISTRY
from modules.providers.persistence.models import (
    ProviderSnapshotModel,
    ProviderUsageModel,
)
from modules.providers.security.secrets import rotate_provider_secret
from modules.providers.tests.test_providers import add_account
from modules.workspaces.domain.models import MembershipStatus, Role
from modules.workspaces.persistence.models import MembershipModel, WorkspaceModel


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
ROOT = Path(__file__).resolve().parents[5]


def _run(coro):
    if sys.platform != "win32":
        return asyncio.run(coro)
    loop = asyncio.SelectorEventLoop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _postgres_url() -> str:
    value = os.getenv("MIGRATION_TEST_DATABASE_URL", "")
    if not value.startswith(("postgresql://", "postgresql+psycopg://")):
        pytest.skip("MIGRATION_TEST_DATABASE_URL does not identify disposable PostgreSQL")
    return value


def _redis_url() -> str:
    value = os.getenv("JOB_TEST_REDIS_URL", "")
    if not value.startswith(("redis://", "rediss://")):
        pytest.skip("JOB_TEST_REDIS_URL does not identify disposable Redis")
    return value


def _require_local_minio() -> None:
    endpoint = os.getenv("OBJECT_STORAGE_S3_ENDPOINT", "")
    if not endpoint.startswith(("http://localhost", "http://127.0.0.1")):
        pytest.skip("OBJECT_STORAGE_S3_ENDPOINT does not identify disposable local MinIO")


def _schema_value(schema: object, *, root: dict | None = None, name: str = "value"):
    """Create a small deterministic value satisfying controlled JSON schemas."""

    if not isinstance(schema, dict):
        return "controlled"
    root = root or schema
    reference = schema.get("$ref")
    if isinstance(reference, str) and reference.startswith("#/"):
        target: object = root
        for part in reference[2:].split("/"):
            if not isinstance(target, dict):
                break
            target = target.get(part.replace("~1", "/").replace("~0", "~"))
        return _schema_value(target, root=root, name=name)
    if "const" in schema:
        return schema["const"]
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return next((value for value in enum if value is not None), enum[0])
    for union_key in ("oneOf", "anyOf"):
        options = schema.get(union_key)
        if isinstance(options, list) and options:
            selected = next(
                (item for item in options if not (isinstance(item, dict) and item.get("type") == "null")),
                options[0],
            )
            return _schema_value(selected, root=root, name=name)
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        schema_type = next((value for value in schema_type if value != "null"), "string")
    if schema_type is None:
        schema_type = "object" if isinstance(schema.get("properties"), dict) else "string"
    if schema_type == "object":
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        required = schema.get("required") if isinstance(schema.get("required"), list) else []
        keys = required or list(properties)
        return {
            key: _schema_value(properties.get(key, {}), root=root, name=str(key))
            for key in keys
        }
    if schema_type == "array":
        minimum = max(1, int(schema.get("minItems") or 1))
        maximum = int(schema.get("maxItems") or minimum)
        count = min(minimum, maximum)
        return [
            _schema_value(schema.get("items", {}), root=root, name=name)
            for _ in range(count)
        ]
    if schema_type in {"integer", "number"}:
        minimum = schema.get("minimum", 0)
        maximum = schema.get("maximum")
        value = minimum if isinstance(minimum, (int, float)) else 0
        if isinstance(maximum, (int, float)):
            value = min(value, maximum)
        return int(value) if schema_type == "integer" else float(value)
    if schema_type == "boolean":
        return True
    if schema_type == "null":
        return None

    lowered = name.lower()
    if schema.get("format") == "uri" or "url" in lowered:
        value = "https://example.com/controlled"
    elif "query" in lowered:
        value = "Bayanly controlled provider architecture"
    elif "image" in lowered and "prompt" in lowered:
        value = "Abstract blue provider architecture illustration"
    elif "speaker" in lowered:
        value = (
            "This controlled speaker note proves that the presentation content "
            "was generated through the normalized text provider execution path."
        )
    elif "title" in lowered or "headline" in lowered:
        value = "Controlled Provider Architecture"
    elif "content" in lowered or "description" in lowered:
        value = "A concise controlled explanation of Bayanly provider routing and managed assets."
    else:
        value = "Controlled value"
    minimum_length = int(schema.get("minLength") or 0)
    while len(value) < minimum_length:
        value += " controlled"
    maximum_length = schema.get("maxLength")
    if isinstance(maximum_length, int):
        value = value[:maximum_length]
    return value


class _ControlledProviderHandler(BaseHTTPRequestHandler):
    calls = {"text": 0, "image": 0, "search": 0}

    def _json(self, status: int, payload: dict) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self):  # noqa: N802 - stdlib handler contract
        size = int(self.headers.get("Content-Length") or "0")
        payload = json.loads(self.rfile.read(size) or b"{}")
        if self.path.endswith("/images/generations"):
            type(self).calls["image"] += 1
            self._json(200, {"data": [{"b64_json": base64.b64encode(PNG_1X1).decode("ascii")} ]})
            return
        if self.path.endswith("/chat/completions"):
            type(self).calls["text"] += 1
            response_format = payload.get("response_format") or {}
            json_schema = response_format.get("json_schema") or {}
            schema = json_schema.get("schema") or {"type": "object"}
            content = json.dumps(_schema_value(schema), ensure_ascii=False)
            self._json(
                200,
                {
                    "id": f"controlled-text-{type(self).calls['text']}",
                    "model": payload.get("model") or "controlled-text",
                    "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 11, "completion_tokens": 7},
                },
            )
            return
        self._json(404, {"error": "not found"})

    def do_GET(self):  # noqa: N802 - stdlib handler contract
        if self.path.startswith("/search"):
            type(self).calls["search"] += 1
            self._json(
                200,
                {
                    "results": [
                        {
                            "title": "Controlled provider source",
                            "url": "https://example.com/provider-source#fragment",
                            "content": "Controlled evidence for the generated deck.",
                        }
                    ]
                },
            )
            return
        self._json(404, {"error": "not found"})

    def log_message(self, _format, *_args) -> None:
        return None


class _Request:
    headers: dict[str, str] = {}
    cookies: dict[str, str] = {}
    state = SimpleNamespace()


class _DiscardTransport:
    """Mark stale disposable-test outbox rows published before this scenario."""

    async def publish(self, _delivery) -> None:
        return None


def test_real_durable_presentation_uses_text_search_image_assets_and_revision(monkeypatch):
    _require_local_minio()
    _ControlledProviderHandler.calls = {"text": 0, "image": 0, "search": 0}
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ControlledProviderHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    origin = f"http://127.0.0.1:{server.server_address[1]}"

    flags = {
        "PROVIDER_REGISTRY_ENABLED": "true",
        "ENCRYPTED_PROVIDER_CONFIG_ENABLED": "true",
        "POLICY_ROUTING_ENABLED": "true",
        "PROVIDER_FALLBACK_ENABLED": "false",
        "LEGACY_PROVIDER_SWITCHES_ENABLED": "true",
        "DURABLE_JOBS_ENABLED": "true",
        "DURABLE_GENERATION_ENABLED": "true",
        "OBJECT_STORAGE_WRITES_ENABLED": "true",
        "ASSET_LIBRARY_ENABLED": "true",
        "CANONICAL_DOCUMENT_WRITES_ENABLED": "true",
        "REVISION_WRITES_ENABLED": "true",
        "WORKSPACES_ENABLED": "true",
        "WORKSPACE_RBAC_ENFORCEMENT_ENABLED": "true",
        "LEGACY_OWNER_BRIDGE_ENABLED": "false",
        "ASSET_SCANNER_MODE": "development",
        "PRESENTON_ENV": "development",
        "OBJECT_STORAGE_PROVIDER": "s3",
        "OBJECT_STORAGE_S3_USE_SSL": "false",
        "OBJECT_STORAGE_S3_ADDRESSING_STYLE": "path",
        "OBJECT_STORAGE_S3_ENCRYPTION": "none",
        "OUTBOUND_HTTP_ALLOWLIST": origin,
        "LLM": "custom",
        "CUSTOM_LLM_MODEL": "controlled-text",
        "PROVIDER_MASTER_KEY_VERSION": "acceptance-v1",
        "PROVIDER_MASTER_KEY": base64.urlsafe_b64encode(b"p" * 32).decode("ascii"),
    }
    for name, value in flags.items():
        monkeypatch.setenv(name, value)
    get_storage_provider.cache_clear()

    async def scenario():
        engine = create_async_engine(_postgres_url(), poolclass=NullPool)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        namespace = f"bayanly:test:provider-presentation:{uuid4().hex}"
        transport = RedisQueueTransport(
            Redis.from_url(_redis_url(), encoding="utf-8", decode_responses=True),
            namespace,
            visibility_seconds=1,
        )
        registry = JobRegistry()
        register_core_handlers(registry)
        register_asset_handlers(registry)
        worker = JobWorker(
            sessions,
            transport,
            registry=registry,
            worker_id="provider-presentation-acceptance",
            lease_seconds=30,
        )
        secret = "controlled-secret-never-serialized"
        owner_token = workspace_token = None
        try:
            from templates.default_templates import _load_default_template
            import services.database as database_service

            # The disposable integration database is shared by focused suites.
            # Drain their already-created outbox rows without injecting them into
            # this test's unique Redis namespace.
            async with sessions() as session:
                while await dispatch_outbox_batch(session, _DiscardTransport()):
                    pass

            suffix = uuid4()
            async with sessions() as session:
                user = User(username=f"provider-e2e-{suffix}", hashed_password="test")
                session.add(user)
                await session.flush()
                workspace = WorkspaceModel(name=f"Provider E2E {suffix}", created_by=user.id)
                session.add(workspace)
                await session.flush()
                session.add(
                    MembershipModel(
                        workspace_id=workspace.id,
                        user_id=user.id,
                        role=Role.OWNER,
                        status=MembershipStatus.ACTIVE,
                    )
                )
                if await session.get(presentation_endpoint.TemplateV2, "general") is None:
                    session.add(_load_default_template(ROOT / "templates" / "general"))

                text_account = await add_account(
                    session,
                    workspace.id,
                    PROVIDER_REGISTRY.get("text.custom"),
                    "Controlled text",
                    model="controlled-text",
                )
                text_account.safe_config = {
                    "base_url": f"{origin}/v1",
                    "price_input_per_million": "1.25",
                    "price_output_per_million": "2.50",
                    "currency": "USD",
                    "pricing_version": "controlled-2026-08",
                }
                image_account = await add_account(
                    session,
                    workspace.id,
                    PROVIDER_REGISTRY.get("image.openai_compatible"),
                    "Controlled image",
                    model="controlled-image",
                )
                image_account.safe_config = {
                    "base_url": f"{origin}/v1",
                    "model": "controlled-image",
                }
                search_account = await add_account(
                    session,
                    workspace.id,
                    PROVIDER_REGISTRY.get("search.searxng"),
                    "Controlled search",
                    model="controlled-search",
                )
                search_account.safe_config = {"base_url": origin}
                await rotate_provider_secret(
                    session,
                    account_id=text_account.id,
                    workspace_id=workspace.id,
                    name="api_key",
                    plaintext=secret,
                )
                await rotate_provider_secret(
                    session,
                    account_id=image_account.id,
                    workspace_id=workspace.id,
                    name="api_key",
                    plaintext=secret,
                )
                await session.commit()
                user_id, workspace_id = user.id, workspace.id

            # Production provider-neutral services resolve their own scoped
            # sessions. NullPool makes this factory safe for the compatibility
            # client's bounded worker thread/event-loop bridge.
            monkeypatch.setattr(database_service, "async_session_maker", sessions)
            monkeypatch.setattr(presentation_endpoint, "async_session_maker", sessions)
            monkeypatch.setattr(
                presentation_endpoint.MEM0_PRESENTATION_MEMORY_SERVICE,
                "store_generation_context",
                AsyncMock(),
            )
            monkeypatch.setattr(
                presentation_endpoint.MEM0_PRESENTATION_MEMORY_SERVICE,
                "store_generated_outlines",
                AsyncMock(),
            )

            async def controlled_export(presentation_id, *_args, **_kwargs):
                return PresentationAndPath(
                    presentation_id=presentation_id,
                    path="/controlled/provider-e2e.pptx",
                )

            monkeypatch.setattr(presentation_endpoint, "export_presentation", controlled_export)
            monkeypatch.setattr(
                presentation_endpoint.CONCURRENT_SERVICE,
                "run_task",
                lambda *_args, **_kwargs: None,
            )

            owner_token = set_current_owner_id(user_id)
            workspace_token = set_current_workspace_id(workspace_id)
            request = GeneratePresentationRequest(
                content="Explain Bayanly's provider architecture with controlled evidence.",
                n_slides=1,
                language="English",
                template="general",
                export_as="pptx",
                web_search=True,
            )
            async with sessions() as session:
                task = await presentation_endpoint.generate_presentation_async(
                    request_http=_Request(),
                    request=request,
                    background_tasks=BackgroundTasks(),
                    idempotency_key=f"provider-e2e-{suffix}",
                    sql_session=session,
                )
                assert task.presentation_id is None
                assert task.resource_id
                generation_job_id = task.durable_job_id
                assert generation_job_id is not None
                generation_job = await session.get(JobModel, generation_job_id)
                assert generation_job is not None
                assert set(generation_job.payload) == {
                    "presentation_id",
                    "legacy_task_id",
                    "request",
                }
                assert secret not in repr(generation_job.payload)

            reset_current_workspace_id(workspace_token)
            reset_current_owner_id(owner_token)
            owner_token = workspace_token = None

            async with sessions() as session:
                assert await dispatch_outbox_batch(session, transport) == 1
            delivery = await transport.consume(QueueClass.GENERATION, timeout=3)
            assert delivery is not None
            assert await worker.handle_delivery(delivery)

            async with sessions() as session:
                # Provider image ingestion creates the only next durable item.
                assert await dispatch_outbox_batch(session, transport) == 1
            scan_delivery = await transport.consume(QueueClass.MAINTENANCE, timeout=3)
            assert scan_delivery is not None
            assert await worker.handle_delivery(scan_delivery)

            presentation_id = UUID(task.resource_id)
            async with sessions() as session:
                generation_job = await session.get(JobModel, generation_job_id)
                compatibility_task = await session.get(AsyncTaskModel, task.id)
                presentation = await session.get(PresentationModel, presentation_id)
                document = await session.scalar(
                    select(PresentationDocumentModel).where(
                        PresentationDocumentModel.presentation_id == presentation_id
                    )
                )
                revisions = list(
                    (
                        await session.scalars(
                            select(PresentationRevisionModel).where(
                                PresentationRevisionModel.presentation_id == presentation_id
                            )
                        )
                    ).all()
                )
                slides = list(
                    (
                        await session.scalars(
                            select(SlideModel).where(SlideModel.presentation == presentation_id)
                        )
                    ).all()
                )
                assets = list(
                    (
                        await session.scalars(
                            select(AssetModel).where(AssetModel.workspace_id == workspace_id)
                        )
                    ).all()
                )
                usage = list(
                    (
                        await session.scalars(
                            select(ProviderUsageModel).where(
                                ProviderUsageModel.workspace_id == workspace_id
                            )
                        )
                    ).all()
                )
                snapshots = list(
                    (
                        await session.scalars(
                            select(ProviderSnapshotModel).where(
                                ProviderSnapshotModel.workspace_id == workspace_id
                            )
                        )
                    ).all()
                )
                jobs = list(
                    (
                        await session.scalars(
                            select(JobModel).where(JobModel.workspace_id == workspace_id)
                        )
                    ).all()
                )
                outbox = list(
                    (
                        await session.scalars(
                            select(OutboxMessageModel).where(
                                OutboxMessageModel.workspace_id == workspace_id
                            )
                        )
                    ).all()
                )

                assert generation_job is not None and generation_job.status == JobStatus.SUCCEEDED
                assert generation_job.attempt_count == 1
                assert compatibility_task is not None
                assert compatibility_task.status == AsyncTaskStatus.COMPLETED
                assert compatibility_task.presentation_id == presentation_id
                assert presentation is not None and presentation.current_revision == 1
                assert document is not None and document.revision == 1 and document.document
                assert len(revisions) == 1 and revisions[0].source == "presentation.generate"
                assert len(slides) == 1
                assert len(assets) == 1 and assets[0].state == AssetState.READY
                assert assets[0].storage_provider == "s3"
                canonical_json = json.dumps(document.document, sort_keys=True)
                assert str(assets[0].id) in canonical_json
                assert assets[0].storage_key not in canonical_json
                assert origin not in canonical_json
                assert all(item.job_id == generation_job_id for item in usage)
                assert {item.family.value for item in usage} == {"TEXT", "IMAGE", "SEARCH"}
                assert {item.operation for item in usage} >= {
                    "presentation.outline",
                    "presentation.structure",
                    "presentation.slide_content",
                    "image.presentation",
                    "search.presentation_outline",
                }
                assert any(item.estimated_cost is not None for item in usage if item.family.value == "TEXT")
                assert len(snapshots) == len(usage)
                assert all(item.status == "SUCCEEDED" for item in usage)
                assert all(secret not in repr(item.payload) for item in jobs)
                assert all(secret not in repr(item.payload) for item in outbox)

            stored = await get_storage_provider("s3").open(assets[0].storage_key)
            assert stored.read().startswith(b"\x89PNG\r\n\x1a\n")
            assert _ControlledProviderHandler.calls["text"] >= 4
            assert _ControlledProviderHandler.calls["image"] == 1
            assert _ControlledProviderHandler.calls["search"] == 1
        finally:
            if workspace_token is not None:
                reset_current_workspace_id(workspace_token)
            if owner_token is not None:
                reset_current_owner_id(owner_token)
            for queue in (QueueClass.GENERATION, QueueClass.MAINTENANCE):
                await transport.client.delete(transport.queue_name(queue))
            await transport.close()
            await engine.dispose()
            get_storage_provider.cache_clear()

    try:
        _run(scenario())
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)
