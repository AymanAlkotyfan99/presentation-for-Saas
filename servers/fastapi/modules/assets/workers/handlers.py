from __future__ import annotations

import io
from uuid import UUID

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func
from sqlmodel import select

from modules.assets.application.scanner import get_malware_scanner
from modules.assets.application.service import add_reference, ingest_bytes
from modules.assets.domain.models import AssetState, MalwareScanStatus, RetentionClass
from modules.assets.persistence.models import AssetModel, AssetReferenceModel
from modules.assets.providers.storage import get_storage_provider
from modules.jobs.domain.models import QueueClass, RetryClass
from modules.jobs.workers.registry import JobRegistry, OperationDefinition
from modules.jobs.workers.runtime import JobExecutionContext, JobHandlerError
from modules.workspaces.domain.models import Permission


class AssetPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: UUID


async def scan_asset(context: JobExecutionContext, payload: AssetPayload) -> dict:
    async with context.worker.session_factory() as session:
        asset = await session.scalar(select(AssetModel).where(AssetModel.id == payload.asset_id).with_for_update())
        if asset is None or asset.workspace_id != context.claim.workspace_id:
            raise JobHandlerError(RetryClass.NON_RETRYABLE_AUTHORIZATION, "ASSET_NOT_FOUND", "Asset was not found")
        if asset.state == AssetState.READY and asset.malware_scan_status == MalwareScanStatus.CLEAN:
            return {"assetId": str(asset.id), "scanStatus": MalwareScanStatus.CLEAN.value}
        if asset.state in {AssetState.REJECTED, AssetState.DELETED}:
            raise JobHandlerError(RetryClass.NON_RETRYABLE_VALIDATION, "ASSET_NOT_SCANNABLE", "Asset is not scannable")
        asset.state = AssetState.SCANNING
        await session.commit()
        provider_id, storage_key, maximum = asset.storage_provider, asset.storage_key, asset.size_bytes
    provider = get_storage_provider(provider_id)
    stream = await provider.open(storage_key)
    try:
        result = await get_malware_scanner().scan(stream, maximum_bytes=maximum)
    finally:
        stream.close()
    async with context.worker.session_factory() as session:
        asset = await session.scalar(select(AssetModel).where(AssetModel.id == payload.asset_id).with_for_update())
        if asset is None or asset.workspace_id != context.claim.workspace_id:
            raise JobHandlerError(RetryClass.NON_RETRYABLE_AUTHORIZATION, "ASSET_NOT_FOUND", "Asset was not found")
        asset.malware_scan_status = result.status
        if result.status == MalwareScanStatus.CLEAN:
            asset.state = AssetState.READY
        elif result.status == MalwareScanStatus.INFECTED:
            asset.state = AssetState.REJECTED
        else:
            asset.state = AssetState.QUARANTINED
        await session.commit()
    if result.status == MalwareScanStatus.UNAVAILABLE:
        raise JobHandlerError(RetryClass.DEPENDENCY_UNAVAILABLE, result.safe_code, "Malware scanner is unavailable")
    if result.status == MalwareScanStatus.ERROR:
        raise JobHandlerError(RetryClass.DEPENDENCY_UNAVAILABLE, result.safe_code, "Malware scan failed")
    if result.status == MalwareScanStatus.INFECTED:
        raise JobHandlerError(RetryClass.NON_RETRYABLE_VALIDATION, result.safe_code, "Asset failed malware policy")
    return {"assetId": str(payload.asset_id), "scanStatus": result.status.value}


async def create_thumbnail(context: JobExecutionContext, payload: AssetPayload) -> dict:
    async with context.worker.session_factory() as session:
        source = await session.get(AssetModel, payload.asset_id)
        if source is None or source.workspace_id != context.claim.workspace_id or source.state != AssetState.READY:
            raise JobHandlerError(RetryClass.NON_RETRYABLE_VALIDATION, "ASSET_NOT_READY", "Asset is not ready")
        if not (source.detected_mime or "").startswith("image/"):
            raise JobHandlerError(RetryClass.NON_RETRYABLE_VALIDATION, "ASSET_NOT_IMAGE", "Asset is not an image")
        provider_id, storage_key, actor_id = source.storage_provider, source.storage_key, source.owner_id
    stream = await get_storage_provider(provider_id).open(storage_key)
    try:
        with Image.open(stream) as image:
            image.thumbnail((512, 512))
            converted = image.convert("RGBA" if image.mode in {"RGBA", "LA"} else "RGB")
            output = io.BytesIO()
            converted.save(output, format="PNG", optimize=True)
            content = output.getvalue()
    except (OSError, ValueError, UnidentifiedImageError) as exc:
        raise JobHandlerError(RetryClass.NON_RETRYABLE_VALIDATION, "THUMBNAIL_INVALID_IMAGE", "Thumbnail source is invalid") from exc
    async with context.worker.session_factory() as session:
        derived = await ingest_bytes(
            session,
            workspace_id=context.claim.workspace_id,
            actor_id=actor_id,
            actor_service_account_id=None,
            data=content,
            filename=f"thumbnail-{payload.asset_id}.png",
            declared_mime="image/png",
            retention_class=RetentionClass.DERIVED,
        )
        await add_reference(
            session,
            asset=derived,
            workspace_id=context.claim.workspace_id,
            resource_type="asset",
            resource_id=str(payload.asset_id),
            reference_type="thumbnail",
            created_by=actor_id,
        )
        await session.commit()
    return {"assetId": str(payload.asset_id), "thumbnailAssetId": str(derived.id)}


async def delete_asset(context: JobExecutionContext, payload: AssetPayload) -> dict:
    async with context.worker.session_factory() as session:
        asset = await session.scalar(select(AssetModel).where(AssetModel.id == payload.asset_id).with_for_update())
        if asset is None or asset.workspace_id != context.claim.workspace_id:
            raise JobHandlerError(RetryClass.NON_RETRYABLE_AUTHORIZATION, "ASSET_NOT_FOUND", "Asset was not found")
        references = await session.scalar(select(func.count(AssetReferenceModel.id)).where(AssetReferenceModel.asset_id == asset.id))
        if references:
            raise JobHandlerError(RetryClass.NON_RETRYABLE_VALIDATION, "ASSET_STILL_REFERENCED", "Asset is still referenced")
        if asset.state == AssetState.DELETED:
            return {"assetId": str(asset.id), "deleted": True}
        asset.state = AssetState.DELETING
        await session.commit()
        provider_id, storage_key = asset.storage_provider, asset.storage_key
    try:
        await get_storage_provider(provider_id).delete(storage_key)
    except FileNotFoundError:
        pass
    async with context.worker.session_factory() as session:
        asset = await session.scalar(select(AssetModel).where(AssetModel.id == payload.asset_id).with_for_update())
        if asset:
            from utils.datetime_utils import get_current_utc_datetime
            asset.state = AssetState.DELETED
            asset.deleted_at = get_current_utc_datetime()
            await session.commit()
    return {"assetId": str(payload.asset_id), "deleted": True}


def register_asset_handlers(registry: JobRegistry) -> None:
    definitions = (
        OperationDefinition(
            "asset.scan", QueueClass.MAINTENANCE, AssetPayload, scan_asset,
            max_attempts=5, required_permissions=(Permission.ASSETS_WRITE,),
        ),
        OperationDefinition(
            "asset.thumbnail", QueueClass.IMAGE, AssetPayload, create_thumbnail,
            max_attempts=3, required_permissions=(Permission.ASSETS_WRITE,),
        ),
        OperationDefinition(
            "asset.delete", QueueClass.MAINTENANCE, AssetPayload, delete_asset,
            max_attempts=3, required_permissions=(Permission.ASSETS_WRITE,),
        ),
    )
    for definition in definitions:
        if registry.get(definition.operation) is None:
            registry.register(definition)
