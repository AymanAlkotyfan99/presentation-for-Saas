from __future__ import annotations

import hashlib
import mimetypes
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Body, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from api.v1.auth.principal import principal_from_request
from modules.assets.application.capabilities import issue_download_capability, verify_download_capability
from modules.assets.application.service import (
    MAX_ASSET_BYTES,
    add_reference,
    complete_upload,
    create_replacement_session,
    create_upload_session,
    ingest_bytes,
    upload_bytes,
)
from modules.assets.domain.models import AssetState, RetentionClass, UploadState
from modules.assets.persistence.models import AssetModel, AssetReferenceModel, UploadSessionModel
from modules.assets.providers.storage import MultipartUpload, get_storage_provider
from modules.jobs.application.submit import JobSubmission, submit_job
from modules.jobs.domain.models import QueueClass
from modules.workspaces.application.authorization import authorize_workspace
from modules.workspaces.domain.models import Permission
from services.database import get_async_session
from utils.api_errors import StableAPIError
from utils.architecture_flags import (
    asset_library_enabled,
    direct_uploads_enabled,
    durable_jobs_enabled,
    object_storage_writes_enabled,
)
from utils.datetime_utils import get_current_utc_datetime


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda value: "".join([value.split("_")[0]] + [part.title() for part in value.split("_")[1:]]),
        populate_by_name=True,
        extra="forbid",
    )


class UploadCreate(CamelModel):
    filename: str | None = Field(default=None, max_length=255)
    mime_type: str = Field(min_length=3, max_length=128)
    size: int = Field(gt=0, le=MAX_ASSET_BYTES)
    checksum_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    multipart: bool = False
    retention_class: RetentionClass = RetentionClass.WORKSPACE


class MultipartComplete(CamelModel):
    parts: list[tuple[int, str]] = Field(min_length=1, max_length=10000)


class ReferenceCreate(CamelModel):
    resource_type: str = Field(min_length=1, max_length=64)
    resource_id: str = Field(min_length=1, max_length=128)
    reference_type: str = Field(min_length=1, max_length=64)


def _require_enabled() -> None:
    if not asset_library_enabled():
        raise StableAPIError(404, "ASSET_LIBRARY_DISABLED", "Asset library is not enabled")


def _require_durable_worker() -> None:
    if not durable_jobs_enabled():
        raise StableAPIError(
            409,
            "DURABLE_JOBS_DISABLED",
            "Durable jobs are required for managed asset operations",
        )


ASSETS_ROUTER = APIRouter(
    prefix="/api/v1/assets", tags=["Assets"], dependencies=[Depends(_require_enabled)]
)


def _asset_json(asset: AssetModel) -> dict:
    return {
        "id": str(asset.id),
        "workspaceId": str(asset.workspace_id),
        "filename": asset.original_filename,
        "size": asset.size_bytes,
        "declaredMime": asset.declared_mime,
        "detectedMime": asset.detected_mime,
        "checksumSha256": asset.checksum_sha256,
        "state": asset.state.value,
        "malwareScanStatus": asset.malware_scan_status.value,
        "retentionClass": asset.retention_class.value,
        "accessibilityMetadata": asset.accessibility_metadata,
        "createdAt": asset.created_at,
        "expiresAt": asset.expires_at,
    }


async def _authorize_current(request: Request, session: AsyncSession, permission: Permission):
    principal = principal_from_request(request)
    if principal.workspace_id is None:
        raise StableAPIError(409, "WORKSPACE_CONTEXT_REQUIRED", "Current workspace is unavailable")
    await authorize_workspace(session, principal=principal, workspace_id=principal.workspace_id, permission=permission)
    return principal


async def _asset(session: AsyncSession, request: Request, asset_id: UUID, permission: Permission, *, lock=False) -> AssetModel:
    statement = select(AssetModel).where(AssetModel.id == asset_id)
    if lock:
        statement = statement.with_for_update()
    asset = await session.scalar(statement)
    if asset is None:
        raise StableAPIError(404, "ASSET_NOT_FOUND", "Asset not found")
    principal = principal_from_request(request)
    await authorize_workspace(
        session, principal=principal, workspace_id=asset.workspace_id,
        permission=permission, resource_workspace_id=asset.workspace_id,
    )
    return asset


@ASSETS_ROUTER.post("/uploads", status_code=201)
async def create_upload(payload: UploadCreate, request: Request, session: AsyncSession = Depends(get_async_session)):
    _require_durable_worker()
    if not object_storage_writes_enabled():
        raise StableAPIError(409, "OBJECT_STORAGE_WRITES_DISABLED", "Object storage writes are not enabled")
    principal = await _authorize_current(request, session, Permission.ASSETS_WRITE)
    asset, upload = await create_upload_session(
        session,
        workspace_id=principal.workspace_id,
        actor_id=principal.user_id,
        actor_service_account_id=principal.service_account_id,
        filename=payload.filename,
        declared_mime=payload.mime_type,
        expected_size=payload.size,
        expected_checksum_sha256=payload.checksum_sha256,
        retention_class=payload.retention_class,
        multipart=payload.multipart,
    )
    direct = None
    provider = get_storage_provider(upload.storage_provider)
    if direct_uploads_enabled() and provider.provider_id == "s3" and not payload.multipart:
        capability = await provider.presign_upload(upload.storage_key, content_type=upload.declared_mime, expires_seconds=300)
        upload.state = UploadState.UPLOADING
        direct = {
            "url": capability.url,
            "method": capability.method,
            "headers": capability.headers,
            "expiresAt": capability.expires_at,
        }
    await session.commit()
    return {
        "asset": _asset_json(asset),
        "uploadSessionId": str(upload.id),
        "expiresAt": upload.expires_at,
        "directUpload": direct,
    }


async def _authorized_upload(session: AsyncSession, request: Request, upload_id: UUID, *, lock=False) -> UploadSessionModel:
    statement = select(UploadSessionModel).where(UploadSessionModel.id == upload_id)
    if lock:
        statement = statement.with_for_update()
    upload = await session.scalar(statement)
    if upload is None:
        raise StableAPIError(404, "UPLOAD_NOT_FOUND", "Upload session not found")
    principal = principal_from_request(request)
    await authorize_workspace(session, principal=principal, workspace_id=upload.workspace_id, permission=Permission.ASSETS_WRITE, resource_workspace_id=upload.workspace_id)
    return upload


async def _bounded_body(request: Request, maximum: int) -> bytes:
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > maximum:
            raise StableAPIError(413, "ASSET_SIZE_INVALID", "Upload exceeds its allowed size")
    return bytes(data)


@ASSETS_ROUTER.put("/uploads/{upload_id}/content")
async def put_upload_content(upload_id: UUID, request: Request, session: AsyncSession = Depends(get_async_session)):
    upload = await _authorized_upload(session, request, upload_id, lock=True)
    data = await _bounded_body(request, min(upload.expected_size, MAX_ASSET_BYTES))
    await upload_bytes(session, upload, data)
    await session.commit()
    return {"uploadSessionId": str(upload.id), "checksumSha256": upload.expected_checksum_sha256}


@ASSETS_ROUTER.put("/uploads/{upload_id}/parts/{part_number}")
async def put_upload_part(upload_id: UUID, part_number: int, request: Request, session: AsyncSession = Depends(get_async_session)):
    upload = await _authorized_upload(session, request, upload_id, lock=True)
    if not upload.multipart or not upload.provider_upload_id:
        raise StableAPIError(409, "UPLOAD_NOT_MULTIPART", "Upload session is not multipart")
    data = await _bounded_body(request, min(upload.expected_size, 20 * 1024 * 1024))
    provider = get_storage_provider(upload.storage_provider)
    asset = await session.get(AssetModel, upload.asset_id)
    etag = await provider.upload_part(MultipartUpload(upload.provider_upload_id, upload.storage_key), part_number, data)
    upload.completed_parts = [item for item in upload.completed_parts if item.get("partNumber") != part_number] + [{"partNumber": part_number, "etag": etag}]
    await session.commit()
    return {"partNumber": part_number, "etag": etag}


@ASSETS_ROUTER.post("/uploads/{upload_id}/multipart-complete")
async def complete_multipart(upload_id: UUID, payload: MultipartComplete, request: Request, session: AsyncSession = Depends(get_async_session)):
    upload = await _authorized_upload(session, request, upload_id, lock=True)
    if not upload.multipart or not upload.provider_upload_id:
        raise StableAPIError(409, "UPLOAD_NOT_MULTIPART", "Upload session is not multipart")
    asset = await session.get(AssetModel, upload.asset_id)
    provider = get_storage_provider(upload.storage_provider)
    await provider.complete_upload(MultipartUpload(upload.provider_upload_id, upload.storage_key), payload.parts)
    upload.state = UploadState.UPLOADING
    completed = await complete_upload(session, upload)
    await session.commit()
    return _asset_json(completed)


@ASSETS_ROUTER.post("/uploads/{upload_id}/complete")
async def complete_upload_endpoint(upload_id: UUID, request: Request, session: AsyncSession = Depends(get_async_session)):
    upload = await _authorized_upload(session, request, upload_id, lock=True)
    asset = await complete_upload(session, upload)
    await session.commit()
    return _asset_json(asset)


@ASSETS_ROUTER.delete("/uploads/{upload_id}", status_code=204)
async def abort_upload(upload_id: UUID, request: Request, session: AsyncSession = Depends(get_async_session)):
    upload = await _authorized_upload(session, request, upload_id, lock=True)
    if upload.multipart and upload.provider_upload_id:
        asset = await session.get(AssetModel, upload.asset_id)
        await get_storage_provider(upload.storage_provider).abort_upload(MultipartUpload(upload.provider_upload_id, asset.storage_key))
    upload.state = UploadState.ABORTED
    upload.aborted_at = get_current_utc_datetime()
    await session.commit()


@ASSETS_ROUTER.get("")
async def list_assets(
    request: Request,
    state: AssetState | None = Query(default=None),
    mime_prefix: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
):
    principal = await _authorize_current(request, session, Permission.ASSETS_READ)
    statement = select(AssetModel).where(AssetModel.workspace_id == principal.workspace_id)
    if state:
        statement = statement.where(AssetModel.state == state)
    if mime_prefix:
        statement = statement.where(AssetModel.detected_mime.startswith(mime_prefix))
    assets = list((await session.scalars(statement.order_by(AssetModel.created_at.desc()).offset(offset).limit(limit))).all())
    return [_asset_json(asset) for asset in assets]


@ASSETS_ROUTER.get("/usage")
async def asset_usage(request: Request, session: AsyncSession = Depends(get_async_session)):
    principal = await _authorize_current(request, session, Permission.ASSETS_READ)
    count, size = (
        await session.execute(
            select(func.count(AssetModel.id), func.coalesce(func.sum(AssetModel.size_bytes), 0)).where(
                AssetModel.workspace_id == principal.workspace_id,
                AssetModel.state != AssetState.DELETED,
            )
        )
    ).one()
    return {"assetCount": count, "bytesRetained": size}


@ASSETS_ROUTER.get("/{asset_id}")
async def get_asset(asset_id: UUID, request: Request, session: AsyncSession = Depends(get_async_session)):
    return _asset_json(await _asset(session, request, asset_id, Permission.ASSETS_READ))


@ASSETS_ROUTER.post("/{asset_id}/replacements", status_code=201)
async def create_replacement(asset_id: UUID, payload: UploadCreate, request: Request, session: AsyncSession = Depends(get_async_session)):
    _require_durable_worker()
    if not object_storage_writes_enabled():
        raise StableAPIError(409, "OBJECT_STORAGE_WRITES_DISABLED", "Object storage writes are not enabled")
    asset = await _asset(session, request, asset_id, Permission.ASSETS_WRITE, lock=True)
    principal = principal_from_request(request)
    upload = await create_replacement_session(
        session,
        asset=asset,
        actor_id=principal.user_id,
        actor_service_account_id=principal.service_account_id,
        declared_mime=payload.mime_type,
        expected_size=payload.size,
        expected_checksum_sha256=payload.checksum_sha256,
        multipart=payload.multipart,
    )
    direct = None
    provider = get_storage_provider(upload.storage_provider)
    if direct_uploads_enabled() and provider.provider_id == "s3" and not payload.multipart:
        capability = await provider.presign_upload(upload.storage_key, content_type=upload.declared_mime, expires_seconds=300)
        upload.state = UploadState.UPLOADING
        direct = {"url": capability.url, "method": capability.method, "headers": capability.headers, "expiresAt": capability.expires_at}
    await session.commit()
    return {"asset": _asset_json(asset), "uploadSessionId": str(upload.id), "targetVersion": upload.target_version, "expiresAt": upload.expires_at, "directUpload": direct}


@ASSETS_ROUTER.post("/{asset_id}/download-capability")
async def download_capability(asset_id: UUID, request: Request, session: AsyncSession = Depends(get_async_session)):
    asset = await _asset(session, request, asset_id, Permission.ASSETS_READ)
    if asset.state != AssetState.READY:
        raise StableAPIError(409, "ASSET_NOT_READY", "Asset is not ready")
    if asset.storage_provider == "s3":
        capability = await get_storage_provider("s3").presign_download(asset.storage_key, expires_seconds=300)
        return {"url": capability.url, "method": capability.method, "expiresAt": capability.expires_at}
    token, expires_at = issue_download_capability(asset.id, asset.workspace_id)
    return {"url": f"/api/v1/assets/{asset.id}/content?token={token}", "method": "GET", "expiresAt": expires_at}


@ASSETS_ROUTER.get("/{asset_id}/content")
async def asset_content(asset_id: UUID, token: str, request: Request, session: AsyncSession = Depends(get_async_session)):
    asset = await _asset(session, request, asset_id, Permission.ASSETS_READ)
    if asset.state != AssetState.READY or not verify_download_capability(token, asset.id, asset.workspace_id):
        raise StableAPIError(403, "ASSET_CAPABILITY_INVALID", "Asset capability is invalid or expired")
    stream = await get_storage_provider(asset.storage_provider).open(asset.storage_key)

    async def chunks():
        try:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            stream.close()

    headers = {"Content-Disposition": f'attachment; filename="asset-{asset.id}"'}
    return StreamingResponse(chunks(), media_type=asset.detected_mime or "application/octet-stream", headers=headers)


@ASSETS_ROUTER.post("/{asset_id}/references", status_code=201)
async def create_reference(asset_id: UUID, payload: ReferenceCreate, request: Request, session: AsyncSession = Depends(get_async_session)):
    asset = await _asset(session, request, asset_id, Permission.ASSETS_WRITE)
    principal = principal_from_request(request)
    reference = await add_reference(
        session, asset=asset, workspace_id=asset.workspace_id,
        resource_type=payload.resource_type, resource_id=payload.resource_id,
        reference_type=payload.reference_type, created_by=principal.user_id,
    )
    await session.commit()
    return {"id": str(reference.id), "assetId": str(reference.asset_id)}


@ASSETS_ROUTER.post("/{asset_id}/copy", status_code=201)
async def copy_asset(asset_id: UUID, request: Request, session: AsyncSession = Depends(get_async_session)):
    source = await _asset(session, request, asset_id, Permission.ASSETS_WRITE)
    if source.state != AssetState.READY:
        raise StableAPIError(409, "ASSET_NOT_READY", "Asset is not ready")
    stream = await get_storage_provider(source.storage_provider).open(source.storage_key)
    try:
        data = stream.read(MAX_ASSET_BYTES + 1)
    finally:
        stream.close()
    principal = principal_from_request(request)
    copied = await ingest_bytes(
        session,
        workspace_id=source.workspace_id,
        actor_id=principal.user_id,
        actor_service_account_id=principal.service_account_id,
        data=data,
        filename=source.original_filename,
        declared_mime=source.detected_mime or source.declared_mime or "application/octet-stream",
        retention_class=source.retention_class,
    )
    await session.commit()
    return _asset_json(copied)


@ASSETS_ROUTER.post("/{asset_id}/thumbnail", status_code=202)
async def thumbnail_asset(asset_id: UUID, request: Request, session: AsyncSession = Depends(get_async_session)):
    _require_durable_worker()
    asset = await _asset(session, request, asset_id, Permission.ASSETS_WRITE)
    principal = principal_from_request(request)
    job, _ = await submit_job(
        session,
        JobSubmission(
            operation="asset.thumbnail", queue_class=QueueClass.IMAGE,
            workspace_id=asset.workspace_id, actor_id=principal.user_id,
            actor_service_account_id=principal.service_account_id,
            idempotency_scope=f"asset.thumbnail:{asset.id}", idempotency_key=str(asset.current_version),
            payload={"asset_id": str(asset.id)}, max_attempts=3,
            resource_type="asset", resource_id=str(asset.id),
        ),
    )
    await session.commit()
    return {"jobId": str(job.id)}


@ASSETS_ROUTER.delete("/{asset_id}", status_code=202)
async def request_asset_delete(asset_id: UUID, request: Request, session: AsyncSession = Depends(get_async_session)):
    _require_durable_worker()
    asset = await _asset(session, request, asset_id, Permission.ASSETS_WRITE, lock=True)
    references = await session.scalar(select(func.count(AssetReferenceModel.id)).where(AssetReferenceModel.asset_id == asset.id))
    if references:
        raise StableAPIError(409, "ASSET_STILL_REFERENCED", "Asset cannot be deleted while referenced")
    principal = principal_from_request(request)
    job, _ = await submit_job(
        session,
        JobSubmission(
            operation="asset.delete", queue_class=QueueClass.MAINTENANCE,
            workspace_id=asset.workspace_id, actor_id=principal.user_id,
            actor_service_account_id=principal.service_account_id,
            idempotency_scope=f"asset.delete:{asset.id}", idempotency_key=str(asset.current_version),
            payload={"asset_id": str(asset.id)}, max_attempts=3,
            resource_type="asset", resource_id=str(asset.id),
        ),
    )
    asset.state = AssetState.DELETING
    await session.commit()
    return {"jobId": str(job.id), "assetId": str(asset.id)}
