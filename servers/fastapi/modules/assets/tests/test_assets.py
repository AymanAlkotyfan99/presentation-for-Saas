import asyncio
import hashlib
import io
import os
from datetime import timedelta
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select

from models.sql.user import User
from models.sql.image_asset import ImageAsset
from api.v1.auth.context import (
    reset_current_owner_id, reset_current_workspace_id,
    set_current_owner_id, set_current_workspace_id,
)
from modules.assets.application.capabilities import issue_download_capability, verify_download_capability
from modules.assets.application.mime import detect_mime, validate_mime
from modules.assets.application.orphans import scan_orphan_candidates
from modules.assets.application.service import add_reference, ingest_bytes
from modules.assets.domain.models import AssetState, MalwareScanStatus
from modules.assets.persistence.models import AssetModel, AssetReferenceModel, ObjectVersionModel, UploadSessionModel
from modules.assets.providers.storage import LocalStorageProvider, MultipartUpload, S3CompatibleStorageProvider
from modules.assets.providers.storage.registry import get_storage_provider
from modules.assets.workers import register_asset_handlers
from modules.jobs.domain.models import JobStatus
from modules.jobs.outbox import dispatch_outbox_batch
from modules.jobs.persistence.models import ConsumerInboxModel, DeadLetterModel, JobAttemptModel, JobEventModel, JobModel, OutboxMessageModel
from modules.jobs.workers.registry import JobRegistry
from modules.jobs.workers.runtime import JobWorker
from modules.workspaces.domain.models import MembershipStatus, Role
from modules.workspaces.persistence.models import MembershipModel, ServiceAccountModel, WorkspaceModel
from utils.api_errors import StableAPIError
from utils.datetime_utils import get_current_utc_datetime


TABLES = (
    User.__table__, WorkspaceModel.__table__, MembershipModel.__table__, ServiceAccountModel.__table__,
    JobModel.__table__, JobAttemptModel.__table__, OutboxMessageModel.__table__,
    ConsumerInboxModel.__table__, DeadLetterModel.__table__, JobEventModel.__table__,
    AssetModel.__table__, ObjectVersionModel.__table__, UploadSessionModel.__table__, AssetReferenceModel.__table__,
    ImageAsset.__table__,
)


class FakeTransport:
    def __init__(self): self.deliveries = []
    async def publish(self, delivery): self.deliveries.append(delivery)
    async def consume(self, _queue_class, timeout=5): return self.deliveries.pop(0) if self.deliveries else None
    async def health(self): return True
    async def close(self): return None


class FakeS3Client:
    def __init__(self):
        self.objects = {}
        self.uploads = {}

    def head_bucket(self, **_kwargs): return {}
    def put_object(self, *, Key, Body, ContentType, Metadata, **_kwargs):
        self.objects[Key] = {"data": bytes(Body), "type": ContentType, "metadata": Metadata}
    def head_object(self, *, Key, **_kwargs):
        value = self.objects[Key]
        return {"ContentLength": len(value["data"]), "ContentType": value["type"], "Metadata": value["metadata"], "ETag": hashlib.sha256(value["data"]).hexdigest()}
    def get_object(self, *, Key, **_kwargs): return {"Body": io.BytesIO(self.objects[Key]["data"])}
    def delete_object(self, *, Key, **_kwargs): self.objects.pop(Key, None)
    def copy_object(self, *, Key, CopySource, **_kwargs): self.objects[Key] = dict(self.objects[CopySource["Key"]])
    def generate_presigned_url(self, operation, *, Params, ExpiresIn, HttpMethod): return f"https://objects.test/{Params['Key']}?operation={operation}&expires={ExpiresIn}&method={HttpMethod}"
    def create_multipart_upload(self, *, Key, ContentType, **_kwargs):
        upload_id = uuid4().hex; self.uploads[upload_id] = {"key": Key, "type": ContentType, "parts": {}}; return {"UploadId": upload_id}
    def upload_part(self, *, UploadId, PartNumber, Body, **_kwargs):
        etag = hashlib.sha256(Body).hexdigest(); self.uploads[UploadId]["parts"][PartNumber] = bytes(Body); return {"ETag": etag}
    def complete_multipart_upload(self, *, UploadId, MultipartUpload, **_kwargs):
        upload = self.uploads.pop(UploadId); data = b"".join(upload["parts"][item["PartNumber"]] for item in MultipartUpload["Parts"]); self.objects[upload["key"]] = {"data": data, "type": upload["type"], "metadata": {}}
    def abort_multipart_upload(self, *, UploadId, **_kwargs): self.uploads.pop(UploadId, None)


async def database(tmp_path, monkeypatch, name="assets.db"):
    storage_root = tmp_path / f"storage-{name}"
    monkeypatch.setenv("OBJECT_STORAGE_PROVIDER", "local")
    monkeypatch.setenv("OBJECT_STORAGE_LOCAL_ROOT", str(storage_root))
    monkeypatch.setenv("DURABLE_JOBS_ENABLED", "true")
    get_storage_provider.cache_clear()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / name}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync: SQLModel.metadata.create_all(sync, tables=TABLES))
    async with sessions() as session:
        user = User(username=f"asset-{name}", hashed_password="test")
        session.add(user)
        await session.flush()
        workspace = WorkspaceModel(name="Assets", created_by=user.id)
        session.add(workspace)
        await session.flush()
        session.add(MembershipModel(workspace_id=workspace.id, user_id=user.id, role=Role.OWNER, status=MembershipStatus.ACTIVE))
        await session.commit()
    return engine, sessions, user.id, workspace.id


def png_bytes(color="red"):
    output = io.BytesIO()
    Image.new("RGB", (8, 8), color).save(output, format="PNG")
    return output.getvalue()


def test_local_storage_contract_traversal_symlink_multipart_and_abort(tmp_path):
    async def scenario():
        provider = LocalStorageProvider(str(tmp_path / "objects"))
        data = b"private-object"
        digest = hashlib.sha256(data).hexdigest()
        metadata = await provider.put_bytes("workspaces/one/assets/two/v000001", data, content_type="text/plain", checksum_sha256=digest)
        assert metadata.size == len(data) and metadata.checksum_sha256 == digest
        assert (await provider.head(metadata.key)).checksum_sha256 == digest
        stream = await provider.open(metadata.key)
        assert stream.read() == data
        stream.close()
        with pytest.raises(ValueError):
            await provider.put_bytes("../escape", data, content_type="text/plain", checksum_sha256=digest)
        with pytest.raises(ValueError):
            await provider.put_bytes("C:\\escape", data, content_type="text/plain", checksum_sha256=digest)

        upload = await provider.begin_upload("workspaces/one/assets/three/v000001", content_type="text/plain")
        first = await provider.upload_part(upload, 1, b"hello ")
        second = await provider.upload_part(upload, 2, b"world")
        complete = await provider.complete_upload(upload, [(1, first), (2, second)])
        assert complete.size == 11
        interrupted = await provider.begin_upload("workspaces/one/assets/four/v000001", content_type="text/plain")
        await provider.upload_part(interrupted, 1, b"partial")
        await provider.abort_upload(interrupted)
        with pytest.raises(FileNotFoundError):
            await provider.head(interrupted.key)
        presigned = await provider.presign_download(metadata.key, expires_seconds=9999)
        assert presigned.method == "GET"
        assert 0 < (presigned.expires_at - get_current_utc_datetime()).total_seconds() <= 901

    asyncio.run(scenario())


def test_local_provider_rejects_symlink_escape_when_supported(tmp_path):
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    link = root / "workspaces"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks is unavailable for this Windows test account")
    provider = LocalStorageProvider(str(root))
    with pytest.raises(ValueError):
        asyncio.run(provider.put_bytes("workspaces/a", b"x", content_type="text/plain", checksum_sha256=hashlib.sha256(b"x").hexdigest()))


def test_s3_compatible_provider_contract_without_live_cloud_calls():
    async def scenario():
        provider = S3CompatibleStorageProvider.__new__(S3CompatibleStorageProvider)
        provider.bucket = "private-test"
        provider.encryption = "AES256"
        provider.client = FakeS3Client()
        assert await provider.health()
        key = "workspaces/one/assets/two/v000001"
        data = b"s3-compatible"
        digest = hashlib.sha256(data).hexdigest()
        stored = await provider.put_bytes(key, data, content_type="text/plain", checksum_sha256=digest)
        assert stored.checksum_sha256 == digest and stored.size == len(data)
        stream = await provider.open(key); assert stream.read() == data
        copied = await provider.copy(key, "workspaces/one/assets/three/v000001")
        assert copied.size == len(data)
        upload = await provider.begin_upload("workspaces/one/assets/four/v000001", content_type="text/plain")
        one = await provider.upload_part(upload, 1, b"one")
        two = await provider.upload_part(upload, 2, b"two")
        completed = await provider.complete_upload(upload, [(1, one), (2, two)])
        assert completed.size == 6
        presigned = await provider.presign_download(key, expires_seconds=3600)
        assert presigned.method == "GET" and "expires=900" in presigned.url
        interrupted = await provider.begin_upload("workspaces/one/assets/five/v000001", content_type="text/plain")
        await provider.abort_upload(interrupted)
        assert interrupted.upload_id not in provider.client.uploads

    asyncio.run(scenario())


def test_mime_spoofing_and_capability_tampering_fail(monkeypatch):
    data = png_bytes()
    assert detect_mime(data) == "image/png"
    validate_mime(declared="image/png", detected="image/png")
    with pytest.raises(ValueError):
        validate_mime(declared="image/jpeg", detected="image/png")
    monkeypatch.setenv("ASSET_CAPABILITY_SIGNING_KEY", "a" * 32)
    asset_id, workspace_id = uuid4(), uuid4()
    token, _ = issue_download_capability(asset_id, workspace_id, expires_seconds=60)
    assert verify_download_capability(token, asset_id, workspace_id)
    assert not verify_download_capability(token + "x", asset_id, workspace_id)
    assert not verify_download_capability(token, asset_id, uuid4())


def test_ingest_quarantines_then_durable_fake_scan_releases_asset(tmp_path, monkeypatch):
    async def scenario():
        engine, sessions, user_id, workspace_id = await database(tmp_path, monkeypatch, "scan.db")
        monkeypatch.setenv("ASSET_SCANNER_MODE", "development")
        monkeypatch.setenv("PRESENTON_ENV", "development")
        content = png_bytes()
        async with sessions() as session:
            asset = await ingest_bytes(
                session,
                workspace_id=workspace_id,
                actor_id=user_id,
                actor_service_account_id=None,
                data=content,
                filename="safe.png",
                declared_mime="image/png",
            )
            await session.commit()
            assert asset.state == AssetState.QUARANTINED
            job = await session.scalar(select(JobModel))
            assert job.payload == {"asset_id": str(asset.id)}
            assert len(str(job.payload).encode()) < 1024
        transport = FakeTransport()
        async with sessions() as session:
            await dispatch_outbox_batch(session, transport)
        registry = JobRegistry()
        register_asset_handlers(registry)
        worker = JobWorker(sessions, transport, registry=registry, worker_id="asset-worker", lease_seconds=10)
        assert await worker.process_delivery(transport.deliveries[0])
        async with sessions() as session:
            current = await session.get(AssetModel, asset.id)
            assert current.state == AssetState.READY
            assert current.malware_scan_status == MalwareScanStatus.CLEAN
            version = await session.scalar(select(ObjectVersionModel).where(ObjectVersionModel.asset_id == asset.id))
            assert version.checksum_sha256 == hashlib.sha256(content).hexdigest()
        await engine.dispose()
        get_storage_provider.cache_clear()

    asyncio.run(scenario())


def test_checksum_mismatch_and_malware_rejection_remain_quarantined_or_rejected(tmp_path, monkeypatch):
    async def scenario():
        engine, sessions, user_id, workspace_id = await database(tmp_path, monkeypatch, "rejection.db")
        from modules.assets.application.service import create_upload_session, upload_bytes
        async with sessions() as session:
            _, upload = await create_upload_session(
                session, workspace_id=workspace_id, actor_id=user_id, actor_service_account_id=None,
                filename="wrong.png", declared_mime="image/png", expected_size=3,
                expected_checksum_sha256="0" * 64,
            )
            with pytest.raises(StableAPIError) as mismatch:
                await upload_bytes(session, upload, b"abc")
            assert mismatch.value.code == "ASSET_CHECKSUM_MISMATCH"
            await session.rollback()

        monkeypatch.setenv("ASSET_SCANNER_MODE", "development")
        malicious = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"
        async with sessions() as session:
            asset = await ingest_bytes(
                session, workspace_id=workspace_id, actor_id=user_id, actor_service_account_id=None,
                data=malicious, filename="sample.txt", declared_mime="text/plain",
            )
            await session.commit()
        transport = FakeTransport()
        async with sessions() as session:
            await dispatch_outbox_batch(session, transport)
        registry = JobRegistry(); register_asset_handlers(registry)
        worker = JobWorker(sessions, transport, registry=registry, worker_id="scanner", lease_seconds=10)
        assert not await worker.process_delivery(transport.deliveries[0])
        async with sessions() as session:
            current = await session.get(AssetModel, asset.id)
            job = await session.scalar(select(JobModel).where(JobModel.resource_id == str(asset.id)))
            assert current.state == AssetState.REJECTED
            assert current.malware_scan_status == MalwareScanStatus.INFECTED
            assert job.status == JobStatus.FAILED
        await engine.dispose(); get_storage_provider.cache_clear()

    asyncio.run(scenario())


def test_cross_workspace_reference_denied_and_orphan_scan_is_read_only(tmp_path, monkeypatch):
    async def scenario():
        engine, sessions, user_id, workspace_id = await database(tmp_path, monkeypatch, "references.db")
        async with sessions() as session:
            asset = await ingest_bytes(
                session, workspace_id=workspace_id, actor_id=user_id, actor_service_account_id=None,
                data=png_bytes(), filename="reference.png", declared_mime="image/png",
            )
            asset.state = AssetState.READY
            asset.created_at = get_current_utc_datetime() - timedelta(days=30)
            await session.commit()
        async with sessions() as session:
            asset = await session.get(AssetModel, asset.id)
            with pytest.raises(StableAPIError):
                await add_reference(
                    session, asset=asset, workspace_id=uuid4(), resource_type="presentation",
                    resource_id="other", reference_type="image", created_by=user_id,
                )
            candidates = await scan_orphan_candidates(session, workspace_id=workspace_id, retention_days=7)
            assert [item.id for item in candidates] == [asset.id]
            assert (await session.get(AssetModel, asset.id)).state == AssetState.READY
            await add_reference(
                session, asset=asset, workspace_id=workspace_id, resource_type="presentation",
                resource_id="one", reference_type="image", created_by=user_id,
            )
            await session.commit()
        async with sessions() as session:
            assert await scan_orphan_candidates(session, workspace_id=workspace_id, retention_days=7) == []
        await engine.dispose(); get_storage_provider.cache_clear()

    asyncio.run(scenario())


def test_replacement_creates_immutable_version_and_preserves_asset_references(tmp_path, monkeypatch):
    async def scenario():
        engine, sessions, user_id, workspace_id = await database(tmp_path, monkeypatch, "replace.db")
        from modules.assets.application.service import create_replacement_session, upload_bytes, complete_upload
        original = png_bytes("red")
        replacement = png_bytes("blue")
        async with sessions() as session:
            asset = await ingest_bytes(
                session, workspace_id=workspace_id, actor_id=user_id, actor_service_account_id=None,
                data=original, filename="versioned.png", declared_mime="image/png",
            )
            asset.state = AssetState.READY
            await add_reference(
                session, asset=asset, workspace_id=workspace_id, resource_type="presentation",
                resource_id="one", reference_type="image", created_by=user_id,
            )
            await session.commit()
        async with sessions() as session:
            asset = await session.get(AssetModel, asset.id)
            upload = await create_replacement_session(
                session, asset=asset, actor_id=user_id, actor_service_account_id=None,
                declared_mime="image/png", expected_size=len(replacement),
                expected_checksum_sha256=hashlib.sha256(replacement).hexdigest(),
            )
            await upload_bytes(session, upload, replacement)
            await complete_upload(session, upload)
            await session.commit()
        async with sessions() as session:
            current = await session.get(AssetModel, asset.id)
            versions = list((await session.scalars(select(ObjectVersionModel).where(ObjectVersionModel.asset_id == asset.id).order_by(ObjectVersionModel.version_number))).all())
            references = list((await session.scalars(select(AssetReferenceModel).where(AssetReferenceModel.asset_id == asset.id))).all())
            assert current.current_version == 2 and current.state == AssetState.QUARANTINED
            assert [item.version_number for item in versions] == [1, 2]
            assert len(references) == 1 and references[0].resource_id == "one"
        await engine.dispose(); get_storage_provider.cache_clear()

    asyncio.run(scenario())


def test_legacy_path_migration_is_dry_run_first_and_retains_original(tmp_path, monkeypatch):
    async def scenario():
        app_data = tmp_path / "app-data"
        monkeypatch.setenv("APP_DATA_DIRECTORY", str(app_data))
        monkeypatch.setenv("WORKSPACE_RBAC_ENFORCEMENT_ENABLED", "true")
        monkeypatch.setenv("LEGACY_OWNER_BRIDGE_ENABLED", "false")
        engine, sessions, user_id, workspace_id = await database(tmp_path, monkeypatch, "legacy.db")
        legacy_dir = app_data / "images" / "workspaces" / str(workspace_id)
        legacy_dir.mkdir(parents=True)
        legacy_path = legacy_dir / "legacy.png"
        legacy_path.write_bytes(png_bytes())
        owner_token = set_current_owner_id(user_id)
        workspace_token = set_current_workspace_id(workspace_id)
        try:
            async with sessions() as session:
                image = ImageAsset(owner_id=user_id, workspace_id=workspace_id, path=str(legacy_path), is_uploaded=True)
                session.add(image); await session.commit()
            from modules.assets.migrations.legacy import inventory_legacy_assets, migrate_legacy_image
            async with sessions() as session:
                inventory = await inventory_legacy_assets(session)
                assert len(inventory) == 1 and inventory[0].exists and not inventory[0].already_migrated
                image = await session.scalar(select(ImageAsset))
                dry_run = await migrate_legacy_image(session, image, dry_run=True)
                assert dry_run["status"] == "would_migrate" and image.asset_id is None
                applied = await migrate_legacy_image(session, image, dry_run=False)
                await session.commit()
                assert applied["status"] == "migrated_original_retained"
                assert legacy_path.exists()
                assert image.asset_id is not None
        finally:
            reset_current_workspace_id(workspace_token)
            reset_current_owner_id(owner_token)
            await engine.dispose(); get_storage_provider.cache_clear()

    asyncio.run(scenario())
