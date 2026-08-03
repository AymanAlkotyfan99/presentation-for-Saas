"""Template query facade; response filtering remains in the HTTP adapter."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.sql.template_v2 import TemplateV2


async def list_template_rows(
    session: AsyncSession, *, default: bool | None
) -> list[Any]:
    query = select(
        TemplateV2.id,
        TemplateV2.name,
        TemplateV2.description,
        TemplateV2.layouts,
        TemplateV2.assets,
        TemplateV2.is_default,
        TemplateV2.created_at,
        TemplateV2.updated_at,
    ).order_by(TemplateV2.created_at.desc())
    if default is not None:
        query = query.where(TemplateV2.is_default == default)
    return list((await session.execute(query)).all())
