"""Dry-run-first legacy local-path read-through and migration."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.sql.image_asset import ImageAsset
from modules.assets.application.mime import detect_mime
from modules.assets.application.service import ingest_bytes
from modules.assets.domain.models import RetentionClass
from utils.api_errors import StableAPIError
from utils.asset_directory_utils import resolve_app_path_to_filesystem


@dataclass(frozen=True)
class LegacyAssetInventory:
    image_asset_id: str
    exists: bool
    size: int | None
    checksum_sha256: str | None
    already_migrated: bool


async def inventory_legacy_assets(session: AsyncSession) -> list[LegacyAssetInventory]:
    rows = list((await session.scalars(select(ImageAsset).order_by(ImageAsset.created_at))).all())
    inventory = []
    for row in rows:
        resolved = resolve_app_path_to_filesystem(row.path)
        checksum = None
        size = None
        if resolved:
            digest = hashlib.sha256()
            with open(resolved, "rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            checksum = digest.hexdigest()
            size = os.path.getsize(resolved)
        inventory.append(LegacyAssetInventory(str(row.id), bool(resolved), size, checksum, row.asset_id is not None))
    return inventory


async def migrate_legacy_image(session: AsyncSession, image: ImageAsset, *, dry_run: bool = True):
    if image.asset_id is not None:
        return {"imageAssetId": str(image.id), "assetId": str(image.asset_id), "status": "already_migrated"}
    resolved = resolve_app_path_to_filesystem(image.path)
    if not resolved:
        raise StableAPIError(404, "LEGACY_ASSET_NOT_FOUND", "Authorized legacy asset was not found")
    with open(resolved, "rb") as stream:
        data = stream.read()
    detected = detect_mime(data)
    if dry_run:
        return {
            "imageAssetId": str(image.id),
            "status": "would_migrate",
            "size": len(data),
            "checksumSha256": hashlib.sha256(data).hexdigest(),
            "detectedMime": detected,
        }
    if image.workspace_id is None:
        raise StableAPIError(409, "LEGACY_ASSET_WORKSPACE_REQUIRED", "Legacy asset must be assigned to a workspace before migration")
    asset = await ingest_bytes(
        session,
        workspace_id=image.workspace_id,
        actor_id=image.owner_id,
        actor_service_account_id=None,
        data=data,
        filename=os.path.basename(resolved),
        declared_mime=detected,
        retention_class=RetentionClass.WORKSPACE,
    )
    image.asset_id = asset.id
    await session.flush()
    return {"imageAssetId": str(image.id), "assetId": str(asset.id), "status": "migrated_original_retained"}
