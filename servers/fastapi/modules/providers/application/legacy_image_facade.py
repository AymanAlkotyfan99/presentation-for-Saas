"""Image facade: Sprint 10 is authoritative; legacy remains rollback-only."""

from __future__ import annotations

from models.image_prompt import ImagePrompt
from modules.providers.application.image_service import ManagedProviderImage, execute_image
from modules.providers.application.runtime import provider_platform_active
from utils.architecture_flags import legacy_provider_switches_enabled


class ProviderImageService:
    def __init__(self, output_directory: str) -> None:
        self.output_directory = output_directory
        self._legacy = None
        if not provider_platform_active():
            if not legacy_provider_switches_enabled():
                raise RuntimeError("Legacy provider switches are disabled")
            from services.image_generation_service import ImageGenerationService

            self._legacy = ImageGenerationService(output_directory)

    async def generate_image(self, prompt: ImagePrompt):
        if self._legacy is not None:
            return await self._legacy.generate_image(prompt)
        values = await execute_image(
            prompt.get_image_prompt(with_theme=True),
            operation="image.presentation",
        )
        return values[0]

    async def get_image_from_pexels(self, query: str, *, api_key: str | None = None, limit: int = 1):
        if self._legacy is not None:
            return await self._legacy.get_image_from_pexels(query, api_key=api_key, limit=limit)
        if api_key:
            raise RuntimeError("Request-scoped provider credentials are forbidden in registry mode")
        return await execute_image(query, count=min(limit, 8), style="stock-search", operation="image.stock_search")

    async def get_image_from_pixabay(self, query: str, *, api_key: str | None = None, limit: int = 1):
        if self._legacy is not None:
            return await self._legacy.get_image_from_pixabay(query, api_key=api_key, limit=limit)
        if api_key:
            raise RuntimeError("Request-scoped provider credentials are forbidden in registry mode")
        return await execute_image(query, count=min(limit, 8), style="stock-search", operation="image.stock_search")


__all__ = ["ManagedProviderImage", "ProviderImageService"]
