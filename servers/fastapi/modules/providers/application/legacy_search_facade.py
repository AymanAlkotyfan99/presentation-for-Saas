"""Provider-facing search facade with an authoritative Sprint 10 path."""

from __future__ import annotations

from enums.web_search_provider import WebSearchProvider
from modules.providers.application.runtime import provider_platform_active
from modules.providers.application.search_service import execute_search
from utils.architecture_flags import legacy_provider_switches_enabled
from utils.web_search import (
    WebSearchResult,
    build_web_search_query,
    format_web_search_context,
)


def _require_legacy() -> None:
    if not legacy_provider_switches_enabled():
        raise RuntimeError("Legacy provider switches are disabled")


def get_selected_web_search_provider() -> WebSearchProvider:
    if provider_platform_active():
        # Selection is intentionally opaque to business code in registry mode.
        return WebSearchProvider.AUTO
    _require_legacy()
    from utils.web_search import get_selected_web_search_provider as legacy

    return legacy()


def should_use_native_web_search() -> bool:
    if provider_platform_active():
        return False
    _require_legacy()
    from utils.web_search import should_use_native_web_search as legacy

    return legacy()


def should_expose_external_web_search_tool(native_search_available: bool = True) -> bool:
    if provider_platform_active():
        return True
    _require_legacy()
    from utils.web_search import should_expose_external_web_search_tool as legacy

    return legacy(native_search_available)


def get_web_search_route(provider=None):
    if provider_platform_active():
        return "provider-platform", None
    _require_legacy()
    from utils.web_search import get_web_search_route as legacy

    return legacy(provider)


async def get_web_search_context(query: str) -> str:
    return format_web_search_context(await get_web_search_results(query))


async def get_web_search_results(query: str) -> list[WebSearchResult]:
    if provider_platform_active():
        result = await execute_search(query, operation="search.presentation_outline")
        return [
            WebSearchResult(
                item.title,
                item.url,
                item.snippet or "",
                item.published_at,
            )
            for item in result.items
        ]
    _require_legacy()
    from utils.web_search import get_web_search_results as legacy

    return await legacy(query)


__all__ = [
    "build_web_search_query", "format_web_search_context",
    "get_selected_web_search_provider",
    "get_web_search_context", "get_web_search_results", "get_web_search_route",
    "should_expose_external_web_search_tool", "should_use_native_web_search",
]
