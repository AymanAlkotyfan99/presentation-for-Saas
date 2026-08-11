"""Trusted, static provider adapter registry.

Database configuration may select registered adapters but can never import or
name arbitrary Python callables.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from enums.image_provider import ImageProvider
from enums.llm_provider import LLMProvider
from enums.web_search_provider import WebSearchProvider
from modules.providers.domain.contracts import (
    CapabilityFamily,
    ProviderAdapter,
    ProviderHealthStatus,
    ProviderRequest,
    ProviderResult,
)


class ProviderExecutionError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message[:512]
        self.retryable = retryable


class CompatibilityAdapter:
    """Contract wrapper for a repository-supported legacy implementation.

    A bridge can be injected by the migrated business service. With no bridge,
    configuration discovery remains available but execution fails closed.
    """

    def __init__(
        self,
        adapter_id: str,
        family: CapabilityFamily,
        *,
        legacy_id: str,
        secret_required: bool,
        execution_bridge: Callable[[ProviderRequest, str | None, dict[str, Any]], Awaitable[ProviderResult]] | None = None,
        connection_bridge: Callable[[str | None, dict[str, Any], float], Awaitable[ProviderHealthStatus]] | None = None,
    ) -> None:
        self.adapter_id = adapter_id
        self.family = family
        self.models = ()
        self.safe_metadata = {
            "legacyId": legacy_id,
            "compatibility": True,
            "secretRequired": secret_required,
            "liveConnectionTest": connection_bridge is not None,
        }
        self._bridge = execution_bridge
        self._connection_bridge = connection_bridge

    async def execute(self, request, *, secret, safe_config):
        if self.safe_metadata["secretRequired"] and not secret:
            raise ProviderExecutionError("CREDENTIALS_MISSING", "Provider credentials are missing", retryable=False)
        if self._bridge is None:
            raise ProviderExecutionError(
                "LEGACY_BRIDGE_REQUIRED",
                "Provider execution remains on the controlled legacy compatibility bridge",
                retryable=False,
            )
        return await self._bridge(request, secret, safe_config)

    async def connection_test(self, *, secret, safe_config, timeout_seconds):
        if self.safe_metadata["secretRequired"] and not secret:
            return ProviderHealthStatus.UNHEALTHY
        if self._connection_bridge is None:
            return ProviderHealthStatus.UNKNOWN
        return await self._connection_bridge(secret, safe_config, timeout_seconds)


class ProviderRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ProviderAdapter] = {}

    def register(self, adapter: ProviderAdapter) -> None:
        if adapter.adapter_id in self._adapters:
            raise ValueError(f"Provider adapter already registered: {adapter.adapter_id}")
        self._adapters[adapter.adapter_id] = adapter

    def get(self, adapter_id: str) -> ProviderAdapter | None:
        return self._adapters.get(adapter_id)

    def list(self, family: CapabilityFamily | None = None) -> tuple[ProviderAdapter, ...]:
        values = self._adapters.values()
        return tuple(sorted((item for item in values if family is None or item.family == family), key=lambda item: item.adapter_id))


def _build_registry() -> ProviderRegistry:
    from modules.providers.adapters.compatibility import (
        connection_test_compatibility,
        execute_image_compatibility,
        execute_search_compatibility,
        execute_text_compatibility,
    )

    registry = ProviderRegistry()
    text_without_required_key = {LLMProvider.OLLAMA, LLMProvider.LMSTUDIO, LLMProvider.CODEX}
    for provider in LLMProvider:
        adapter_id = f"text.{provider.value}"
        registry.register(
            CompatibilityAdapter(
                adapter_id, CapabilityFamily.TEXT,
                legacy_id=provider.value, secret_required=provider not in text_without_required_key,
                execution_bridge=lambda request, secret, config, adapter_id=adapter_id: execute_text_compatibility(adapter_id, request, secret, config),
                connection_bridge=lambda secret, config, timeout, adapter_id=adapter_id: connection_test_compatibility(adapter_id, CapabilityFamily.TEXT, secret, config, timeout),
            )
        )
    image_without_required_key = {ImageProvider.COMFYUI}
    for provider in ImageProvider:
        adapter_id = f"image.{provider.value}"
        registry.register(
            CompatibilityAdapter(
                adapter_id, CapabilityFamily.IMAGE,
                legacy_id=provider.value, secret_required=provider not in image_without_required_key,
                execution_bridge=lambda request, secret, config, adapter_id=adapter_id: execute_image_compatibility(adapter_id, request, secret, config),
                connection_bridge=lambda secret, config, timeout, adapter_id=adapter_id: connection_test_compatibility(adapter_id, CapabilityFamily.IMAGE, secret, config, timeout),
            )
        )
    search_without_required_key = {WebSearchProvider.AUTO, WebSearchProvider.NATIVE, WebSearchProvider.SEARXNG}
    for provider in WebSearchProvider:
        adapter_id = f"search.{provider.value}"
        executable = provider not in {WebSearchProvider.AUTO, WebSearchProvider.NATIVE}
        registry.register(
            CompatibilityAdapter(
                adapter_id, CapabilityFamily.SEARCH,
                legacy_id=provider.value, secret_required=provider not in search_without_required_key,
                execution_bridge=(lambda request, secret, config, adapter_id=adapter_id: execute_search_compatibility(adapter_id, request, secret, config)) if executable else None,
                connection_bridge=(lambda secret, config, timeout, adapter_id=adapter_id: connection_test_compatibility(adapter_id, CapabilityFamily.SEARCH, secret, config, timeout)) if executable else None,
            )
        )
    return registry


PROVIDER_REGISTRY = _build_registry()
