"""Provider-neutral production image service returning managed assets only."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from api.v1.auth.context import get_current_job_id, get_current_workspace_id
from modules.providers.application.executor import ProviderExecutor
from modules.providers.domain.contracts import ImageAIRequest


@dataclass(frozen=True)
class ManagedProviderImage:
    asset_id: UUID
    state: str = "QUARANTINED"


async def execute_image(
    prompt: str,
    *,
    count: int = 1,
    style: str | None = None,
    operation: str = "image.business",
) -> list[ManagedProviderImage]:
    workspace_id = get_current_workspace_id()
    if workspace_id is None:
        raise RuntimeError("Provider execution requires an active workspace context")
    from services.database import async_session_maker

    async with async_session_maker() as session:
        result = await ProviderExecutor().execute(
            session,
            workspace_id=workspace_id,
            request=ImageAIRequest(prompt=prompt, count=count, style=style),
            job_id=get_current_job_id(),
            operation=operation,
        )
    return [ManagedProviderImage(asset_id=value) for value in result.asset_ids]
