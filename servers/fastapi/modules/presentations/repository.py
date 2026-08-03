"""Persistence facade for presentation CRUD operations.

The facade intentionally returns SQL models. Moving response models or data
ownership is a later migration; this seam first removes database orchestration
from the transport layer without changing transactions or response shapes.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.sql.presentation import PresentationModel, PresentationVersion
from models.sql.slide import SlideModel
from utils.architecture_flags import (
    legacy_v1_reads_enabled,
    require_legacy_v1_read,
    require_legacy_v1_write,
)


async def list_presentation_rows(
    session: AsyncSession,
    *,
    version: PresentationVersion | None,
    include_slides: bool,
) -> list[Any]:
    if version is not None:
        require_legacy_v1_read(version)
    if include_slides:
        query = select(PresentationModel, SlideModel).join(
            SlideModel,
            (SlideModel.presentation == PresentationModel.id) & (SlideModel.index == 0),
        )
    else:
        query = select(PresentationModel)
    if version is not None:
        query = query.where(PresentationModel.version == version)
    elif not legacy_v1_reads_enabled():
        query = query.where(PresentationModel.version != PresentationVersion.V1_STANDARD)
    result = await session.execute(query.order_by(PresentationModel.created_at.desc()))
    return list(result.all() if include_slides else result.scalars().all())


async def load_presentation_with_slides(
    session: AsyncSession, presentation_id: uuid.UUID
) -> tuple[PresentationModel | None, list[SlideModel]]:
    presentation = await session.get(PresentationModel, presentation_id)
    if presentation is None:
        return None, []
    require_legacy_v1_read(presentation.version)
    slides = list(
        await session.scalars(
            select(SlideModel)
            .where(SlideModel.presentation == presentation_id)
            .order_by(SlideModel.index)
        )
    )
    return presentation, slides


async def delete_presentation_record(
    session: AsyncSession, presentation: PresentationModel
) -> None:
    require_legacy_v1_write(presentation.version)
    await session.delete(presentation)
    await session.commit()


async def duplicate_presentation_record(
    session: AsyncSession,
    presentation: PresentationModel,
    slides: list[SlideModel],
) -> tuple[PresentationModel, list[SlideModel]]:
    require_legacy_v1_read(presentation.version)
    require_legacy_v1_write(presentation.version)
    duplicate = presentation.get_new_presentation()
    if duplicate.title:
        duplicate.title = f"{duplicate.title} (Copy)"
    duplicate_slides = [slide.get_new_slide(duplicate.id) for slide in slides]
    session.add(duplicate)
    session.add_all(duplicate_slides)
    await session.commit()
    await session.refresh(duplicate)
    return duplicate, duplicate_slides
