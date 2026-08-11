from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from modules.assets.domain.models import AssetState
from modules.assets.persistence.models import AssetModel, AssetReferenceModel
from utils.datetime_utils import get_current_utc_datetime


async def scan_orphan_candidates(
    session: AsyncSession,
    *,
    workspace_id,
    retention_days: int = 7,
) -> list[AssetModel]:
    """Read-only candidate scan. This function never deletes objects."""
    cutoff = get_current_utc_datetime() - timedelta(days=max(1, retention_days))
    references = (
        select(AssetReferenceModel.asset_id, func.count(AssetReferenceModel.id).label("reference_count"))
        .where(AssetReferenceModel.workspace_id == workspace_id)
        .group_by(AssetReferenceModel.asset_id)
        .subquery()
    )
    return list(
        (
            await session.scalars(
                select(AssetModel)
                .outerjoin(references, references.c.asset_id == AssetModel.id)
                .where(
                    AssetModel.workspace_id == workspace_id,
                    AssetModel.created_at <= cutoff,
                    AssetModel.state.in_([AssetState.READY, AssetState.REJECTED, AssetState.EXPIRED]),
                    func.coalesce(references.c.reference_count, 0) == 0,
                )
                .order_by(AssetModel.created_at)
            )
        ).all()
    )
