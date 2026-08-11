from __future__ import annotations

import hashlib
import os
from datetime import timedelta
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from modules.assets.application.mime import detect_mime, normalize_declared_mime, validate_mime
from modules.assets.domain.models import AssetState, MalwareScanStatus, RetentionClass, UploadState
from modules.assets.persistence.models import AssetModel, AssetReferenceModel, ObjectVersionModel, UploadSessionModel
from modules.assets.providers.storage import get_storage_provider
from modules.jobs.application.submit import JobSubmission, submit_job
from modules.jobs.domain.models import QueueClass
from utils.api_errors import StableAPIError
from utils.architecture_flags import durable_jobs_enabled
from utils.datetime_utils import get_current_utc_datetime


MAX_ASSET_BYTES = 100 * 1024 * 1024
UPLOAD_TTL_SECONDS = 60 * 60


def safe_original_filename(value: str | None) -> str | None:
    if not value:
        return None
    name = os.path.basename(value.replace("\\", "/")).strip()
    if not name or name in {".", ".."}:
        return None
    return name[:255]


def object_key(workspace_id: UUID, asset_id: UUID, version: int = 1) -> str:
    return f"workspaces/{workspace_id}/assets/{asset_id}/v{version:06d}"


async def create_upload_session(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    actor_id: UUID | None,
    actor_service_account_id: UUID | None,
    filename: str | None,
    declared_mime: str,
    expected_size: int,
    expected_checksum_sha256: str | None = None,
    retention_class: RetentionClass = RetentionClass.WORKSPACE,
    multipart: bool = False,
    storage_provider_id: str | None = None,
) -> tuple[AssetModel, UploadSessionModel]:
    declared = normalize_declared_mime(declared_mime)
    if expected_size < 1 or expected_size > MAX_ASSET_BYTES:
        raise StableAPIError(413, "ASSET_SIZE_INVALID", "Asset size is outside the allowed range")
    if expected_checksum_sha256 is not None and (
        len(expected_checksum_sha256) != 64
        or any(char not in "0123456789abcdefABCDEF" for char in expected_checksum_sha256)
    ):
        raise StableAPIError(422, "ASSET_CHECKSUM_INVALID", "Asset checksum is invalid")
    provider = get_storage_provider(storage_provider_id)
    asset = AssetModel(
        workspace_id=workspace_id,
        owner_id=actor_id,
        creator_service_account_id=actor_service_account_id,
        storage_provider=provider.provider_id,
        storage_key="pending",
        original_filename=safe_original_filename(filename),
        declared_mime=declared,
        size_bytes=expected_size,
        state=AssetState.UPLOADING,
        retention_class=retention_class,
    )
    asset.storage_key = object_key(workspace_id, asset.id)
    upload = UploadSessionModel(
        asset_id=asset.id,
        workspace_id=workspace_id,
        actor_id=actor_id,
        actor_service_account_id=actor_service_account_id,
        storage_provider=provider.provider_id,
        storage_key=asset.storage_key,
        target_version=1,
        state=UploadState.CREATED,
        expected_size=expected_size,
        expected_checksum_sha256=expected_checksum_sha256.lower() if expected_checksum_sha256 else None,
        declared_mime=declared,
        multipart=multipart,
        expires_at=get_current_utc_datetime() + timedelta(seconds=UPLOAD_TTL_SECONDS),
    )
    if multipart:
        started = await provider.begin_upload(upload.storage_key, content_type=declared)
        upload.provider_upload_id = started.upload_id
        upload.state = UploadState.UPLOADING
    session.add(asset)
    session.add(upload)
    await session.flush()
    return asset, upload


async def upload_bytes(session: AsyncSession, upload: UploadSessionModel, data: bytes) -> None:
    if upload.state not in {UploadState.CREATED, UploadState.UPLOADING} or upload.multipart:
        raise StableAPIError(409, "UPLOAD_STATE_INVALID", "Upload session cannot accept this content")
    if len(data) != upload.expected_size:
        raise StableAPIError(422, "ASSET_SIZE_MISMATCH", "Uploaded object size does not match the session")
    checksum = hashlib.sha256(data).hexdigest()
    if upload.expected_checksum_sha256 and checksum != upload.expected_checksum_sha256:
        raise StableAPIError(422, "ASSET_CHECKSUM_MISMATCH", "Uploaded object checksum does not match")
    asset = await session.get(AssetModel, upload.asset_id)
    if asset is None or asset.workspace_id != upload.workspace_id:
        raise StableAPIError(404, "ASSET_NOT_FOUND", "Asset not found")
    provider = get_storage_provider(upload.storage_provider)
    await provider.put_bytes(upload.storage_key, data, content_type=upload.declared_mime, checksum_sha256=checksum)
    upload.state = UploadState.UPLOADING
    upload.expected_checksum_sha256 = checksum
    await session.flush()


async def complete_upload(session: AsyncSession, upload: UploadSessionModel) -> AssetModel:
    if not durable_jobs_enabled():
        raise StableAPIError(
            409,
            "DURABLE_JOBS_DISABLED",
            "Durable jobs must be enabled before an asset enters quarantine scanning",
        )
    now = get_current_utc_datetime()
    if upload.expires_at.tzinfo is None:
        expires_at = upload.expires_at.replace(tzinfo=now.tzinfo)
    else:
        expires_at = upload.expires_at
    if expires_at <= now:
        upload.state = UploadState.EXPIRED
        raise StableAPIError(409, "UPLOAD_EXPIRED", "Upload session has expired")
    if upload.state != UploadState.UPLOADING:
        raise StableAPIError(409, "UPLOAD_STATE_INVALID", "Upload is not ready to complete")
    asset = await session.get(AssetModel, upload.asset_id)
    if asset is None or asset.workspace_id != upload.workspace_id:
        raise StableAPIError(404, "ASSET_NOT_FOUND", "Asset not found")
    provider = get_storage_provider(upload.storage_provider)
    metadata = await provider.head(upload.storage_key)
    if metadata.size != upload.expected_size:
        raise StableAPIError(422, "ASSET_SIZE_MISMATCH", "Stored object size does not match the session")
    stream = await provider.open(upload.storage_key)
    try:
        data = stream.read(MAX_ASSET_BYTES + 1)
    finally:
        stream.close()
    if len(data) > MAX_ASSET_BYTES:
        raise StableAPIError(413, "ASSET_SIZE_INVALID", "Stored asset exceeds its size limit")
    checksum = hashlib.sha256(data).hexdigest()
    if upload.expected_checksum_sha256 and checksum != upload.expected_checksum_sha256:
        raise StableAPIError(422, "ASSET_CHECKSUM_MISMATCH", "Stored object checksum does not match")
    detected = detect_mime(data)
    try:
        validate_mime(declared=upload.declared_mime, detected=detected)
    except ValueError as exc:
        asset.state = AssetState.REJECTED
        asset.detected_mime = detected
        asset.size_bytes = metadata.size
        asset.checksum_sha256 = checksum
        upload.state = UploadState.ABORTED
        upload.aborted_at = now
        # Persist the quarantine/rejection evidence even though the caller
        # receives a validation error; object bytes remain private.
        await session.commit()
        raise StableAPIError(422, "ASSET_MIME_MISMATCH", str(exc)) from exc
    asset.size_bytes = metadata.size
    asset.checksum_sha256 = checksum
    asset.detected_mime = detected
    asset.state = AssetState.QUARANTINED
    asset.malware_scan_status = MalwareScanStatus.PENDING
    asset.storage_key = upload.storage_key
    asset.current_version = upload.target_version
    upload.state = UploadState.COMPLETED
    upload.completed_at = now
    session.add(
        ObjectVersionModel(
            asset_id=asset.id,
            workspace_id=asset.workspace_id,
            version_number=upload.target_version,
            storage_provider=asset.storage_provider,
            storage_key=upload.storage_key,
            checksum_sha256=checksum,
            size_bytes=asset.size_bytes,
            detected_mime=detected,
        )
    )
    await submit_job(
        session,
        JobSubmission(
            operation="asset.scan",
            queue_class=QueueClass.MAINTENANCE,
            workspace_id=asset.workspace_id,
            actor_id=upload.actor_id,
            actor_service_account_id=upload.actor_service_account_id,
            idempotency_scope=f"asset.scan:{asset.id}",
            idempotency_key=checksum,
            payload={"asset_id": str(asset.id)},
            max_attempts=5,
            resource_type="asset",
            resource_id=str(asset.id),
        ),
    )
    await session.flush()
    return asset


async def ingest_bytes(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    actor_id: UUID | None,
    actor_service_account_id: UUID | None,
    data: bytes,
    filename: str | None,
    declared_mime: str,
    retention_class: RetentionClass = RetentionClass.WORKSPACE,
    storage_provider_id: str | None = None,
) -> AssetModel:
    asset, upload = await create_upload_session(
        session,
        workspace_id=workspace_id,
        actor_id=actor_id,
        actor_service_account_id=actor_service_account_id,
        filename=filename,
        declared_mime=declared_mime,
        expected_size=len(data),
        expected_checksum_sha256=hashlib.sha256(data).hexdigest(),
        retention_class=retention_class,
        storage_provider_id=storage_provider_id,
    )
    await upload_bytes(session, upload, data)
    return await complete_upload(session, upload)


async def create_replacement_session(
    session: AsyncSession,
    *,
    asset: AssetModel,
    actor_id: UUID | None,
    actor_service_account_id: UUID | None,
    declared_mime: str,
    expected_size: int,
    expected_checksum_sha256: str | None = None,
    multipart: bool = False,
) -> UploadSessionModel:
    if asset.state != AssetState.READY:
        raise StableAPIError(409, "ASSET_NOT_READY", "Only a ready asset may be replaced")
    declared = normalize_declared_mime(declared_mime)
    if expected_size < 1 or expected_size > MAX_ASSET_BYTES:
        raise StableAPIError(413, "ASSET_SIZE_INVALID", "Asset size is outside the allowed range")
    if expected_checksum_sha256 is not None and len(expected_checksum_sha256) != 64:
        raise StableAPIError(422, "ASSET_CHECKSUM_INVALID", "Asset checksum is invalid")
    target_version = asset.current_version + 1
    provider = get_storage_provider(asset.storage_provider)
    upload = UploadSessionModel(
        asset_id=asset.id,
        workspace_id=asset.workspace_id,
        actor_id=actor_id,
        actor_service_account_id=actor_service_account_id,
        storage_provider=asset.storage_provider,
        storage_key=object_key(asset.workspace_id, asset.id, target_version),
        target_version=target_version,
        state=UploadState.CREATED,
        expected_size=expected_size,
        expected_checksum_sha256=expected_checksum_sha256.lower() if expected_checksum_sha256 else None,
        declared_mime=declared,
        multipart=multipart,
        expires_at=get_current_utc_datetime() + timedelta(seconds=UPLOAD_TTL_SECONDS),
    )
    if multipart:
        started = await provider.begin_upload(upload.storage_key, content_type=declared)
        upload.provider_upload_id = started.upload_id
        upload.state = UploadState.UPLOADING
    session.add(upload)
    await session.flush()
    return upload


async def ingest_file(session: AsyncSession, *, path: str, declared_mime: str, **kwargs) -> AssetModel:
    with open(path, "rb") as stream:
        data = stream.read(MAX_ASSET_BYTES + 1)
    if len(data) > MAX_ASSET_BYTES:
        raise StableAPIError(413, "ASSET_SIZE_INVALID", "Asset exceeds its size limit")
    return await ingest_bytes(
        session,
        data=data,
        filename=os.path.basename(path),
        declared_mime=declared_mime,
        **kwargs,
    )


async def add_reference(
    session: AsyncSession,
    *,
    asset: AssetModel,
    workspace_id: UUID,
    resource_type: str,
    resource_id: str,
    reference_type: str,
    created_by: UUID | None,
) -> AssetReferenceModel:
    if asset.workspace_id != workspace_id:
        raise StableAPIError(404, "ASSET_NOT_FOUND", "Asset not found")
    reference = AssetReferenceModel(
        workspace_id=workspace_id,
        asset_id=asset.id,
        resource_type=resource_type[:64],
        resource_id=resource_id[:128],
        reference_type=reference_type[:64],
        created_by=created_by,
    )
    session.add(reference)
    await session.flush()
    return reference
