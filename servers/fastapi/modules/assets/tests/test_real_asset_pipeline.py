"""Cross-sprint asset pipeline coverage with PostgreSQL, Redis, and MinIO."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys
from uuid import UUID, uuid4

import pytest
from botocore.exceptions import ClientError
from PIL import Image
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select

from api.v1.auth.context import (
    reset_current_owner_id,
    reset_current_workspace_id,
    set_current_owner_id,
    set_current_workspace_id,
)
from api.v1.ppt.endpoints.presentation_document import _validate_asset_ownership
from models.sql.presentation import PresentationModel, PresentationVersion
from models.sql.user import User
from modules.assets.application.service import (
    complete_upload,
    create_upload_session,
    ingest_bytes,
    upload_bytes,
)
from modules.assets.domain.models import AssetState, MalwareScanStatus, UploadState
from modules.assets.persistence.models import (
    AssetModel,
    AssetReferenceModel,
    ObjectVersionModel,
)
from modules.assets.providers.storage.registry import get_storage_provider
from modules.assets.workers import register_asset_handlers
from modules.jobs.application.submit import JobSubmission, submit_job
from modules.jobs.domain.models import JobStatus, QueueClass
from modules.jobs.outbox import RedisQueueTransport, dispatch_outbox_batch
from modules.jobs.persistence.models import JobModel
from modules.jobs.workers.registry import JobRegistry
from modules.jobs.workers.handlers.core import register_core_handlers
from modules.jobs.workers.runtime import JobWorker
from modules.presentations.domain import validate_presentation_document
from modules.presentations.revision_service import write_snapshot_revision
from modules.providers.adapters.registry import ProviderRegistry
from modules.providers.application.executor import ProviderExecutor
from modules.providers.domain.contracts import (
    CapabilityFamily,
    ImageAIRequest,
    ImageAIResult,
    ProviderHealthStatus,
    RegionPolicyStatus,
    UsageUnits,
)
from modules.providers.persistence.models import (
    ProviderAccountModel,
    ProviderCapabilityModel,
    ProviderHealthModel,
)
from modules.workspaces.domain.models import MembershipStatus, Role
from modules.workspaces.persistence.models import MembershipModel, WorkspaceModel
from utils.api_errors import StableAPIError


ROOT = Path(__file__).resolve().parents[5]
IMAGE_DOCUMENT = json.loads(
    (ROOT / "schemas/presentation-document/fixtures/valid/image-slide.json").read_text(
        encoding="utf-8"
    )
)


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


def _configure_minio(monkeypatch) -> None:
    endpoint = os.getenv("OBJECT_STORAGE_S3_ENDPOINT", "")
    if not endpoint.startswith(("http://localhost", "http://127.0.0.1")):
        pytest.skip("OBJECT_STORAGE_S3_ENDPOINT does not identify disposable local MinIO")
    monkeypatch.setenv("OBJECT_STORAGE_PROVIDER", "s3")
    monkeypatch.setenv("OBJECT_STORAGE_S3_USE_SSL", "false")
    monkeypatch.setenv("OBJECT_STORAGE_S3_ADDRESSING_STYLE", "path")
    monkeypatch.setenv("OBJECT_STORAGE_S3_ENCRYPTION", "none")
    monkeypatch.setenv("DURABLE_JOBS_ENABLED", "true")
    monkeypatch.setenv("ASSET_SCANNER_MODE", "development")
    monkeypatch.setenv("PRESENTON_ENV", "development")
    get_storage_provider.cache_clear()


def _png_bytes(color: str = "red") -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (32, 24), color).save(output, format="PNG")
    return output.getvalue()


async def _identity(sessions):
    suffix = uuid4()
    async with sessions() as session:
        user = User(username=f"asset-real-{suffix}", hashed_password="test")
        session.add(user)
        await session.flush()
        workspace = WorkspaceModel(name=f"Asset real {suffix}", created_by=user.id)
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
        await session.commit()
        return user.id, workspace.id


def test_real_asset_scan_thumbnail_and_minio_identity(monkeypatch):
    async def scenario():
        _configure_minio(monkeypatch)
        engine = create_async_engine(_postgres_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        user_id, workspace_id = await _identity(sessions)
        namespace = f"bayanly:test:assets:{uuid4().hex}"
        transport = RedisQueueTransport(
            Redis.from_url(_redis_url(), encoding="utf-8", decode_responses=True),
            namespace,
            visibility_seconds=1,
        )
        registry = JobRegistry()
        register_asset_handlers(registry)
        worker = JobWorker(
            sessions,
            transport,
            registry=registry,
            worker_id="real-asset-worker",
            lease_seconds=10,
        )
        provider = get_storage_provider("s3")
        try:
            source_bytes = _png_bytes()
            async with sessions() as session:
                source = await ingest_bytes(
                    session,
                    workspace_id=workspace_id,
                    actor_id=user_id,
                    actor_service_account_id=None,
                    data=source_bytes,
                    filename="source.png",
                    declared_mime="image/png",
                )
                await session.commit()
                assert source.state == AssetState.QUARANTINED
                assert source.storage_provider == "s3"
                assert source.storage_key == (
                    f"workspaces/{workspace_id}/assets/{source.id}/v000001"
                )
            async with sessions() as session:
                assert await dispatch_outbox_batch(session, transport) == 1
            scan_delivery = await transport.consume(QueueClass.MAINTENANCE, timeout=2)
            assert scan_delivery is not None
            assert await worker.handle_delivery(scan_delivery)
            async with sessions() as session:
                source_row = await session.get(AssetModel, source.id)
                assert source_row is not None and source_row.state == AssetState.READY
                assert source_row.malware_scan_status == MalwareScanStatus.CLEAN
                thumbnail_job, _ = await submit_job(
                    session,
                    JobSubmission(
                        operation="asset.thumbnail",
                        queue_class=QueueClass.IMAGE,
                        workspace_id=workspace_id,
                        actor_id=user_id,
                        actor_service_account_id=None,
                        idempotency_scope=f"asset.thumbnail:{source.id}",
                        idempotency_key=str(source_row.current_version),
                        payload={"asset_id": str(source.id)},
                        resource_type="asset",
                        resource_id=str(source.id),
                    ),
                )
                await session.commit()
            async with sessions() as session:
                assert await dispatch_outbox_batch(session, transport) == 1
            thumbnail_delivery = await transport.consume(QueueClass.IMAGE, timeout=2)
            assert thumbnail_delivery is not None
            assert await worker.handle_delivery(thumbnail_delivery)
            async with sessions() as session:
                completed_job = await session.get(JobModel, thumbnail_job.id)
                assert completed_job is not None
                assert completed_job.status == JobStatus.SUCCEEDED
                assert completed_job.payload == {"asset_id": str(source.id)}
                assert len(str(completed_job.payload).encode("utf-8")) < 1024
                thumbnail_id = UUID(completed_job.result["thumbnailAssetId"])
                thumbnail = await session.get(AssetModel, thumbnail_id)
                version = await session.scalar(
                    select(ObjectVersionModel).where(
                        ObjectVersionModel.asset_id == thumbnail_id
                    )
                )
                reference = await session.scalar(
                    select(AssetReferenceModel).where(
                        AssetReferenceModel.asset_id == thumbnail_id
                    )
                )
                assert thumbnail is not None and thumbnail.storage_provider == "s3"
                assert version is not None and version.storage_key == thumbnail.storage_key
                assert reference is not None
                assert reference.resource_id == str(source.id)
                assert reference.reference_type == "thumbnail"
            thumbnail_bytes = (await provider.open(thumbnail.storage_key)).read()
            assert thumbnail_bytes.startswith(b"\x89PNG\r\n\x1a\n")
            # The derived asset also follows quarantine -> durable scan -> READY.
            async with sessions() as session:
                assert await dispatch_outbox_batch(session, transport) == 1
            derived_scan = await transport.consume(QueueClass.MAINTENANCE, timeout=2)
            assert derived_scan is not None
            assert await worker.handle_delivery(derived_scan)
            async with sessions() as session:
                ready_thumbnail = await session.get(AssetModel, thumbnail_id)
                assert ready_thumbnail is not None
                assert ready_thumbnail.state == AssetState.READY
        finally:
            for queue in (QueueClass.MAINTENANCE, QueueClass.IMAGE):
                await transport.client.delete(transport.queue_name(queue))
            await transport.close()
            await engine.dispose()
            get_storage_provider.cache_clear()

    _run(scenario())


def test_real_minio_mime_checksum_and_safe_scanner_rejection(monkeypatch):
    async def scenario():
        _configure_minio(monkeypatch)
        engine = create_async_engine(_postgres_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        user_id, workspace_id = await _identity(sessions)
        namespace = f"bayanly:test:asset-policy:{uuid4().hex}"
        transport = RedisQueueTransport(
            Redis.from_url(_redis_url(), encoding="utf-8", decode_responses=True),
            namespace,
            visibility_seconds=1,
        )
        registry = JobRegistry()
        register_asset_handlers(registry)
        worker = JobWorker(sessions, transport, registry=registry, worker_id="scanner")
        provider = get_storage_provider("s3")
        try:
            content = _png_bytes("blue")
            async with sessions() as session:
                mismatch_asset, mismatch_upload = await create_upload_session(
                    session,
                    workspace_id=workspace_id,
                    actor_id=user_id,
                    actor_service_account_id=None,
                    filename="spoofed.jpg",
                    declared_mime="image/jpeg",
                    expected_size=len(content),
                    expected_checksum_sha256=hashlib.sha256(content).hexdigest(),
                )
                await upload_bytes(session, mismatch_upload, content)
                with pytest.raises(StableAPIError) as mime_error:
                    await complete_upload(session, mismatch_upload)
                assert mime_error.value.code == "ASSET_MIME_MISMATCH"
                assert mismatch_asset.state == AssetState.REJECTED
                assert mismatch_upload.state == UploadState.ABORTED

            async with sessions() as session:
                checksum_asset, checksum_upload = await create_upload_session(
                    session,
                    workspace_id=workspace_id,
                    actor_id=user_id,
                    actor_service_account_id=None,
                    filename="checksum.png",
                    declared_mime="image/png",
                    expected_size=len(content),
                    expected_checksum_sha256="0" * 64,
                )
                with pytest.raises(StableAPIError) as checksum_error:
                    await upload_bytes(session, checksum_upload, content)
                assert checksum_error.value.code == "ASSET_CHECKSUM_MISMATCH"
                await session.rollback()
            with pytest.raises(ClientError):
                await provider.head(checksum_asset.storage_key)

            safe_test_signature = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"
            async with sessions() as session:
                infected = await ingest_bytes(
                    session,
                    workspace_id=workspace_id,
                    actor_id=user_id,
                    actor_service_account_id=None,
                    data=safe_test_signature,
                    filename="eicar-test.txt",
                    declared_mime="text/plain",
                )
                await session.commit()
            async with sessions() as session:
                assert await dispatch_outbox_batch(session, transport) == 1
            delivery = await transport.consume(QueueClass.MAINTENANCE, timeout=2)
            assert delivery is not None
            assert not await worker.handle_delivery(delivery)
            async with sessions() as session:
                rejected = await session.get(AssetModel, infected.id)
                scan_job = await session.scalar(
                    select(JobModel).where(JobModel.resource_id == str(infected.id))
                )
                assert rejected is not None and rejected.state == AssetState.REJECTED
                assert rejected.malware_scan_status == MalwareScanStatus.INFECTED
                assert scan_job is not None and scan_job.status == JobStatus.FAILED
        finally:
            await transport.client.delete(transport.queue_name(QueueClass.MAINTENANCE))
            await transport.close()
            await engine.dispose()
            get_storage_provider.cache_clear()

    _run(scenario())


def test_controlled_image_provider_creates_managed_minio_asset_and_canonical_reference(
    monkeypatch,
):
    async def scenario():
        _configure_minio(monkeypatch)
        monkeypatch.setenv("POLICY_ROUTING_ENABLED", "true")
        monkeypatch.setenv("PROVIDER_FALLBACK_ENABLED", "false")
        monkeypatch.setenv("WORKSPACE_RBAC_ENFORCEMENT_ENABLED", "true")
        monkeypatch.setenv("LEGACY_OWNER_BRIDGE_ENABLED", "false")
        engine = create_async_engine(_postgres_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        user_id, workspace_id = await _identity(sessions)
        namespace = f"bayanly:test:image-provider:{uuid4().hex}"
        transport = RedisQueueTransport(
            Redis.from_url(_redis_url(), encoding="utf-8", decode_responses=True),
            namespace,
            visibility_seconds=1,
        )
        provider = get_storage_provider("s3")

        class ControlledImageAdapter:
            adapter_id = "image.controlled-managed"
            family = CapabilityFamily.IMAGE
            models = ("image-a",)
            safe_metadata = {"secretRequired": False, "controlled": True}

            async def execute(self, request, *, secret, safe_config):
                del secret, safe_config
                assert isinstance(request, ImageAIRequest)
                async with sessions() as asset_session:
                    asset = await ingest_bytes(
                        asset_session,
                        workspace_id=workspace_id,
                        actor_id=user_id,
                        actor_service_account_id=None,
                        data=_png_bytes("green"),
                        filename="controlled-provider.png",
                        declared_mime="image/png",
                    )
                    await asset_session.commit()
                return ImageAIResult(
                    asset_ids=[asset.id],
                    model="image-a",
                    usage=UsageUnits(images=1),
                )

            async def connection_test(
                self, *, secret, safe_config, timeout_seconds
            ):
                del secret, safe_config, timeout_seconds
                return ProviderHealthStatus.HEALTHY

        owner_token = set_current_owner_id(user_id)
        workspace_token = set_current_workspace_id(workspace_id)
        registry = ProviderRegistry()
        adapter = ControlledImageAdapter()
        registry.register(adapter)
        try:
            async with sessions() as session:
                account = ProviderAccountModel(
                    workspace_id=workspace_id,
                    adapter_id=adapter.adapter_id,
                    name="Controlled image provider",
                    default_model="image-a",
                    region_policy_status=RegionPolicyStatus.ALLOWED,
                )
                session.add(account)
                await session.flush()
                session.add_all([
                    ProviderCapabilityModel(
                        provider_account_id=account.id,
                        workspace_id=workspace_id,
                        family=CapabilityFamily.IMAGE,
                        model="image-a",
                    ),
                    ProviderHealthModel(
                        provider_account_id=account.id,
                        workspace_id=workspace_id,
                    ),
                ])
                await session.commit()

            async with sessions() as session:
                result = await ProviderExecutor(registry=registry).execute(
                    session,
                    workspace_id=workspace_id,
                    request=ImageAIRequest(
                        prompt="Controlled local diagram", model="image-a"
                    ),
                    pinned_account_id=account.id,
                )
                assert result.usage.images == 1
                assert result.provider_snapshot_id is not None
                asset_id = result.asset_ids[0]
                asset = await session.get(AssetModel, asset_id)
                assert asset is not None and asset.state == AssetState.QUARANTINED
                assert (await provider.open(asset.storage_key)).read().startswith(
                    b"\x89PNG\r\n\x1a\n"
                )

            registry_jobs = JobRegistry()
            register_asset_handlers(registry_jobs)
            worker = JobWorker(
                sessions,
                transport,
                registry=registry_jobs,
                worker_id="controlled-image-scanner",
            )
            async with sessions() as session:
                assert await dispatch_outbox_batch(session, transport) == 1
            delivery = await transport.consume(QueueClass.MAINTENANCE, timeout=2)
            assert delivery is not None and await worker.handle_delivery(delivery)

            presentation_id = uuid4()
            async with sessions() as session:
                ready = await session.get(AssetModel, asset_id)
                assert ready is not None and ready.state == AssetState.READY
                session.add(PresentationModel(
                    id=presentation_id,
                    owner_id=user_id,
                    workspace_id=workspace_id,
                    version=PresentationVersion.V2_STANDARD,
                    content="Controlled provider asset",
                    n_slides=1,
                    language="en",
                    title="Controlled provider asset",
                ))
                await session.commit()

            payload = copy.deepcopy(IMAGE_DOCUMENT)
            payload["presentationId"] = str(presentation_id)
            payload["assets"][0]["assetId"] = str(asset_id)
            payload["slides"][0]["elements"][0]["assetId"] = str(asset_id)
            document = validate_presentation_document(payload)
            async with sessions() as session:
                await _validate_asset_ownership(session, document, None)
                revision = await write_snapshot_revision(
                    session,
                    presentation_id=presentation_id,
                    actor_id=user_id,
                    document=document.model_dump(
                        mode="json", by_alias=True, exclude_none=True
                    ),
                    expected_revision=0,
                    idempotency_key=f"controlled-image:{asset_id}",
                    source="controlled-provider-test",
                )
                assert revision.revision.revision == 1
                assert revision.document["assets"][0]["assetId"] == str(asset_id)
        finally:
            reset_current_workspace_id(workspace_token)
            reset_current_owner_id(owner_token)
            await transport.client.delete(
                transport.queue_name(QueueClass.MAINTENANCE)
            )
            await transport.close()
            await engine.dispose()
            get_storage_provider.cache_clear()

    _run(scenario())


def test_controlled_export_job_returns_managed_asset_without_local_path(
    monkeypatch, tmp_path
):
    async def scenario():
        _configure_minio(monkeypatch)
        monkeypatch.setenv("OBJECT_STORAGE_WRITES_ENABLED", "true")
        monkeypatch.setenv("WORKSPACE_RBAC_ENFORCEMENT_ENABLED", "true")
        monkeypatch.setenv("LEGACY_OWNER_BRIDGE_ENABLED", "false")
        engine = create_async_engine(_postgres_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        user_id, workspace_id = await _identity(sessions)
        namespace = f"bayanly:test:export-asset:{uuid4().hex}"
        transport = RedisQueueTransport(
            Redis.from_url(_redis_url(), encoding="utf-8", decode_responses=True),
            namespace,
            visibility_seconds=1,
        )
        export_file = tmp_path / "controlled-export.pdf"
        export_file.write_bytes(b"%PDF-1.4\n% controlled local export\n%%EOF\n")

        async def controlled_export(*_args, **_kwargs):
            return SimpleNamespace(path=str(export_file))

        import utils.export_utils as export_utils

        monkeypatch.setattr(export_utils, "export_presentation", controlled_export)
        owner_token = set_current_owner_id(user_id)
        workspace_token = set_current_workspace_id(workspace_id)
        registry = JobRegistry()
        register_core_handlers(registry)
        register_asset_handlers(registry)
        worker = JobWorker(
            sessions,
            transport,
            registry=registry,
            worker_id="controlled-export-worker",
        )
        try:
            presentation_id = uuid4()
            async with sessions() as session:
                session.add(PresentationModel(
                    id=presentation_id,
                    owner_id=user_id,
                    workspace_id=workspace_id,
                    version=PresentationVersion.V2_STANDARD,
                    content="Controlled export",
                    n_slides=1,
                    language="en",
                    title="Controlled export",
                    current_revision=1,
                ))
                await session.commit()
                job, _ = await submit_job(
                    session,
                    JobSubmission(
                        operation="presentation.export",
                        queue_class=QueueClass.EXPORT,
                        workspace_id=workspace_id,
                        actor_id=user_id,
                        actor_service_account_id=None,
                        idempotency_scope=f"presentation.export:{presentation_id}",
                        idempotency_key="revision-1-pdf",
                        payload={
                            "presentation_id": str(presentation_id),
                            "source_revision": 1,
                            "title": "Controlled export",
                            "export_as": "pdf",
                        },
                        resource_type="presentation",
                        resource_id=str(presentation_id),
                        source_revision=1,
                    ),
                )
                await session.commit()
            async with sessions() as session:
                assert await dispatch_outbox_batch(session, transport) == 1
            delivery = await transport.consume(QueueClass.EXPORT, timeout=2)
            assert delivery is not None and await worker.handle_delivery(delivery)
            async with sessions() as session:
                completed = await session.get(JobModel, job.id)
                assert completed is not None and completed.status == JobStatus.SUCCEEDED
                assert set(completed.result) == {"assetId"}
                asset_id = UUID(completed.result["assetId"])
                asset = await session.get(AssetModel, asset_id)
                reference = await session.scalar(select(AssetReferenceModel).where(
                    AssetReferenceModel.asset_id == asset_id,
                    AssetReferenceModel.workspace_id == workspace_id,
                ))
                assert asset is not None and asset.storage_provider == "s3"
                assert asset.state == AssetState.QUARANTINED
                assert reference is not None
                assert reference.resource_id == str(presentation_id)
                assert reference.reference_type == "export"
                assert (await get_storage_provider("s3").open(asset.storage_key)).read() == export_file.read_bytes()
            async with sessions() as session:
                assert await dispatch_outbox_batch(session, transport) == 1
            scan = await transport.consume(QueueClass.MAINTENANCE, timeout=2)
            assert scan is not None and await worker.handle_delivery(scan)
            async with sessions() as session:
                ready = await session.get(AssetModel, asset_id)
                assert ready is not None and ready.state == AssetState.READY
        finally:
            reset_current_workspace_id(workspace_token)
            reset_current_owner_id(owner_token)
            for queue in (QueueClass.EXPORT, QueueClass.MAINTENANCE):
                await transport.client.delete(transport.queue_name(queue))
            await transport.close()
            await engine.dispose()
            get_storage_provider.cache_clear()

    _run(scenario())
