import os
from unittest.mock import AsyncMock, Mock, patch

import pytest

from services.image_generation_service import ImageGenerationService


class TestImageGenerationOpenAICompatible:
    @pytest.fixture
    def anyio_backend(self):
        return "asyncio"

    @pytest.fixture
    def mock_images_directory(self, tmp_path):
        images_dir = tmp_path / "images"
        images_dir.mkdir()
        return str(images_dir)

    @staticmethod
    def _session(generation_payload: dict, image_bytes: bytes | None = None):
        generation = Mock(status=200)
        generation.json = AsyncMock(return_value=generation_payload)
        session = AsyncMock()
        session.post = AsyncMock(return_value=generation)
        if image_bytes is not None:
            download = Mock(status=200)
            download.read = AsyncMock(return_value=image_bytes)
            session.get = AsyncMock(return_value=download)
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)
        return session

    @staticmethod
    def _config():
        return (
            patch("services.image_generation_service.get_openai_compat_image_base_url_env", return_value="https://api.example.com/v1"),
            patch("services.image_generation_service.get_openai_compat_image_api_key_env", return_value="sk-test-key"),
            patch("services.image_generation_service.get_openai_compat_image_model_env", return_value="custom-model"),
        )

    def test_get_image_gen_func_openai_compatible_selected(self, mock_images_directory):
        with patch("services.image_generation_service.is_image_generation_disabled", return_value=False), patch("services.image_generation_service.is_openai_compatible_selected", return_value=True), patch("services.image_generation_service.is_pixabay_selected", return_value=False), patch("services.image_generation_service.is_pixels_selected", return_value=False), patch("services.image_generation_service.is_gemini_flash_selected", return_value=False), patch("services.image_generation_service.is_nanobanana_pro_selected", return_value=False), patch("services.image_generation_service.is_dalle3_selected", return_value=False), patch("services.image_generation_service.is_gpt_image_1_5_selected", return_value=False), patch("services.image_generation_service.is_comfyui_selected", return_value=False), patch("services.image_generation_service.is_open_webui_selected", return_value=False):
            service = ImageGenerationService(mock_images_directory)
        assert service.image_gen_func == service.generate_image_openai_compatible

    @pytest.mark.anyio
    async def test_generate_image_openai_compatible_success(self, mock_images_directory):
        service = ImageGenerationService(mock_images_directory)
        b64_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        session = self._session({"data": [{"b64_json": b64_image}]})
        base, key, model = self._config()
        with base, key, model, patch("services.image_generation_service.SecureClientSession", return_value=session):
            image_path = await service.generate_image_openai_compatible("test prompt", mock_images_directory)
        session.post.assert_awaited_once()
        assert session.post.call_args.args[0] == "https://api.example.com/v1/images/generations"
        assert session.post.call_args.kwargs["json"] == {"model": "custom-model", "prompt": "test prompt", "n": 1, "size": "1024x1024"}
        assert session.post.call_args.kwargs["headers"]["Authorization"] == "Bearer sk-test-key"
        assert os.path.exists(image_path) and image_path.startswith(mock_images_directory)

    @pytest.mark.anyio
    async def test_generate_image_openai_compatible_missing_config(self, mock_images_directory):
        service = ImageGenerationService(mock_images_directory)
        with patch("services.image_generation_service.get_openai_compat_image_base_url_env", return_value=None):
            with pytest.raises(ValueError, match="OPENAI_COMPAT_IMAGE_BASE_URL"):
                await service.generate_image_openai_compatible("test prompt", mock_images_directory)

    @pytest.mark.anyio
    async def test_generate_image_openai_compatible_missing_model(self, mock_images_directory):
        service = ImageGenerationService(mock_images_directory)
        with patch("services.image_generation_service.get_openai_compat_image_base_url_env", return_value="https://api.example.com/v1"), patch("services.image_generation_service.get_openai_compat_image_api_key_env", return_value="sk-test-key"), patch("services.image_generation_service.get_openai_compat_image_model_env", return_value=None):
            with pytest.raises(ValueError, match="OPENAI_COMPAT_IMAGE_BASE_URL"):
                await service.generate_image_openai_compatible("test prompt", mock_images_directory)

    async def _url_case(self, mock_images_directory: str, returned_url: str):
        service = ImageGenerationService(mock_images_directory)
        session = self._session({"data": [{"url": returned_url}]}, b"\x89PNG\r\n\x1a\n")
        base, key, model = self._config()
        with base, key, model, patch("services.image_generation_service.SecureClientSession", return_value=session):
            image_path = await service.generate_image_openai_compatible("test prompt", mock_images_directory)
        return session, image_path

    @pytest.mark.anyio
    async def test_generate_image_openai_compatible_url_response(self, mock_images_directory):
        session, image_path = await self._url_case(mock_images_directory, "https://api.example.com/images/result.png")
        assert session.get.call_args.kwargs["headers"] == {"Authorization": "Bearer sk-test-key"}
        assert os.path.exists(image_path)

    @pytest.mark.anyio
    async def test_generate_image_openai_compatible_relative_url_response(self, mock_images_directory):
        session, image_path = await self._url_case(mock_images_directory, "/images/result.png")
        assert session.get.call_args.args[0] == "https://api.example.com/images/result.png"
        assert session.get.call_args.kwargs["headers"] == {"Authorization": "Bearer sk-test-key"}
        assert os.path.exists(image_path)

    @pytest.mark.anyio
    async def test_generate_image_openai_compatible_cross_origin_url_skips_auth(self, mock_images_directory):
        session, image_path = await self._url_case(mock_images_directory, "https://cdn.example.net/images/result.png")
        assert session.get.call_args.kwargs["headers"] == {}
        assert os.path.exists(image_path)
