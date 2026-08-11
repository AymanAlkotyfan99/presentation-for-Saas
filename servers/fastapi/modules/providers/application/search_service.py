"""Provider-neutral production search service."""

from __future__ import annotations

from api.v1.auth.context import get_current_job_id, get_current_workspace_id
from modules.providers.application.executor import ProviderExecutor
from modules.providers.domain.contracts import SearchRequest, SearchResult


async def execute_search(
    query: str,
    *,
    result_count: int = 5,
    language: str | None = None,
    region: str | None = None,
    operation: str = "search.business",
) -> SearchResult:
    workspace_id = get_current_workspace_id()
    if workspace_id is None:
        raise RuntimeError("Provider execution requires an active workspace context")
    from services.database import async_session_maker

    async with async_session_maker() as session:
        return await ProviderExecutor().execute(
            session,
            workspace_id=workspace_id,
            request=SearchRequest(
                query=query,
                result_count=result_count,
                language=language,
                region=region,
            ),
            job_id=get_current_job_id(),
            operation=operation,
        )
