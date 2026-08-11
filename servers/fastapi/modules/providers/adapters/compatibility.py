"""Official adapters that contain legacy SDK implementations behind Sprint 10.

Nothing in this module is a business-level routing decision.  The selected
adapter is already fixed by ProviderExecutor; task-local environment overrides
only translate the selected account into the legacy SDK's configuration shape.
"""

from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
import os
import tempfile
from typing import Any
from urllib.parse import urlparse

import aiohttp

from modules.providers.adapters.registry import ProviderExecutionError
from modules.providers.domain.contracts import (
    CapabilityFamily,
    ImageAIAdapterResult,
    ImageAIRequest,
    ImageProviderOutput,
    NormalizedToolCall,
    ProviderHealthStatus,
    SearchItem,
    SearchRequest,
    SearchResult,
    TextAIRequest,
    TextAIResult,
    UsageUnits,
)
from utils.get_env import provider_environment


_SECRET_ENV = {
    "text.openai": "OPENAI_API_KEY",
    "text.deepseek": "DEEPSEEK_API_KEY",
    "text.google": "GOOGLE_API_KEY",
    "text.vertex": "VERTEX_API_KEY",
    "text.azure": "AZURE_OPENAI_API_KEY",
    "text.bedrock": "BEDROCK_AWS_SECRET_ACCESS_KEY",
    "text.openrouter": "OPENROUTER_API_KEY",
    "text.fireworks": "FIREWORKS_API_KEY",
    "text.together": "TOGETHER_API_KEY",
    "text.cerebras": "CEREBRAS_API_KEY",
    "text.anthropic": "ANTHROPIC_API_KEY",
    "text.litellm": "LITELLM_API_KEY",
    "text.lmstudio": "LMSTUDIO_API_KEY",
    "text.custom": "CUSTOM_LLM_API_KEY",
    "image.pexels": "PEXELS_API_KEY",
    "image.pixabay": "PIXABAY_API_KEY",
    "image.gemini_flash": "GOOGLE_API_KEY",
    "image.nanobanana_pro": "GOOGLE_API_KEY",
    "image.dall-e-3": "OPENAI_API_KEY",
    "image.gpt-image-1.5": "OPENAI_API_KEY",
    "image.open_webui": "OPEN_WEBUI_IMAGE_API_KEY",
    "image.openai_compatible": "OPENAI_COMPAT_IMAGE_API_KEY",
    "search.tavily": "TAVILY_API_KEY",
    "search.exa": "EXA_API_KEY",
    "search.brave": "BRAVE_SEARCH_API_KEY",
    "search.serper": "SERPER_API_KEY",
}

_SAFE_CONFIG_ENV = {
    "text.deepseek": {"base_url": "DEEPSEEK_BASE_URL"},
    "text.vertex": {"base_url": "VERTEX_BASE_URL", "project": "VERTEX_PROJECT", "location": "VERTEX_LOCATION"},
    "text.azure": {"base_url": "AZURE_OPENAI_BASE_URL", "endpoint": "AZURE_OPENAI_ENDPOINT", "api_version": "AZURE_OPENAI_API_VERSION", "deployment": "AZURE_OPENAI_DEPLOYMENT"},
    "text.bedrock": {"region": "BEDROCK_REGION", "access_key_id": "BEDROCK_AWS_ACCESS_KEY_ID", "session_token": "BEDROCK_AWS_SESSION_TOKEN", "profile_name": "BEDROCK_PROFILE_NAME"},
    "text.openrouter": {"base_url": "OPENROUTER_BASE_URL"},
    "text.fireworks": {"base_url": "FIREWORKS_BASE_URL"},
    "text.together": {"base_url": "TOGETHER_BASE_URL"},
    "text.cerebras": {"base_url": "CEREBRAS_BASE_URL"},
    "text.litellm": {"base_url": "LITELLM_BASE_URL"},
    "text.lmstudio": {"base_url": "LMSTUDIO_BASE_URL"},
    "text.ollama": {"base_url": "OLLAMA_URL"},
    "text.custom": {"base_url": "CUSTOM_LLM_URL"},
    "text.codex": {"account_id": "CODEX_ACCOUNT_ID", "expires": "CODEX_TOKEN_EXPIRES"},
    "image.comfyui": {"base_url": "COMFYUI_URL", "workflow": "COMFYUI_WORKFLOW"},
    "image.open_webui": {"base_url": "OPEN_WEBUI_IMAGE_URL"},
    "image.openai_compatible": {"base_url": "OPENAI_COMPAT_IMAGE_BASE_URL", "model": "OPENAI_COMPAT_IMAGE_MODEL"},
    "search.searxng": {"base_url": "SEARXNG_BASE_URL"},
}


def _secret_values(secret: str | None) -> dict[str, str]:
    if not secret:
        return {}
    try:
        payload = json.loads(secret)
    except (TypeError, ValueError):
        return {"value": secret}
    if not isinstance(payload, dict):
        return {"value": secret}
    return {str(key): str(value) for key, value in payload.items() if value is not None}


def compatibility_environment(adapter_id: str, secret: str | None, safe_config: dict[str, Any]) -> dict[str, str | None]:
    family, legacy_id = adapter_id.split(".", 1)
    values: dict[str, str | None] = {}
    if family == "text":
        values["LLM"] = legacy_id
        if adapter_id == "text.bedrock":
            values["AWS_MAX_ATTEMPTS"] = "1"
    elif family == "image":
        values["IMAGE_PROVIDER"] = legacy_id
    elif family == "search":
        values["WEB_SEARCH_PROVIDER"] = legacy_id

    secrets = _secret_values(secret)
    secret_env = _SECRET_ENV.get(adapter_id)
    if secret_env:
        values[secret_env] = secrets.get("value") or secrets.get("api_key") or secret
    for key, env_name in _SAFE_CONFIG_ENV.get(adapter_id, {}).items():
        if key in safe_config and safe_config[key] is not None:
            values[env_name] = str(safe_config[key])

    # Multi-value credentials stay inside the encrypted JSON envelope.
    secret_aliases = {
        "api_key": secret_env,
        "access_token": "CODEX_ACCESS_TOKEN",
        "refresh_token": "CODEX_REFRESH_TOKEN",
        "account_id": "CODEX_ACCOUNT_ID",
        "expires": "CODEX_TOKEN_EXPIRES",
        "access_key_id": "BEDROCK_AWS_ACCESS_KEY_ID",
        "secret_access_key": "BEDROCK_AWS_SECRET_ACCESS_KEY",
        "session_token": "BEDROCK_AWS_SESSION_TOKEN",
    }
    for key, value in secrets.items():
        env_name = secret_aliases.get(key)
        if env_name:
            values[env_name] = value
    return values


def _disable_sdk_retries(client: Any) -> None:
    """Keep ProviderExecutor as the only transport retry/fallback authority."""

    underlying = getattr(client, "_client", None)
    with_options = getattr(underlying, "with_options", None)
    if callable(with_options):
        try:
            client._client = with_options(max_retries=0)
        except (TypeError, ValueError):
            # SDKs without this supported option use their configured one-shot path.
            pass


def _legacy_message(payload: dict[str, Any]):
    from llmai.shared import AssistantMessage, AssistantToolCall, SystemMessage, ToolResponseMessage, UserMessage

    role = payload.get("role")
    if role == "system":
        return SystemMessage(content=str(payload.get("content") or ""))
    if role == "assistant":
        calls = [AssistantToolCall.model_validate(item) for item in payload.get("tool_calls", [])]
        return AssistantMessage(id=payload.get("id"), content=payload.get("content"), tool_calls=calls)
    if role == "tool":
        return ToolResponseMessage(id=str(payload.get("id") or "tool"), content=payload.get("content"))
    content = payload.get("content") or ""
    if isinstance(content, list):
        restored: list[Any] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("data"), dict) and "__bayanly_base64__" in item["data"]:
                item = dict(item)
                item["data"] = base64.b64decode(item["data"]["__bayanly_base64__"], validate=True)
            restored.append(item)
        content = restored
    return UserMessage.model_validate({"content": content})


def _legacy_tools(payloads: list[dict[str, Any]]) -> list[Any]:
    from llmai.shared import Tool

    return [Tool.model_validate(payload) for payload in payloads]


def _usage(response: Any) -> UsageUnits:
    raw = getattr(response, "usage", None)
    if raw is None:
        return UsageUnits()
    return UsageUnits(
        input_tokens=getattr(raw, "input_tokens", None) or getattr(raw, "prompt_tokens", None),
        output_tokens=getattr(raw, "output_tokens", None) or getattr(raw, "completion_tokens", None),
    )


def _provider_error(exc: BaseException) -> ProviderExecutionError:
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    name = type(exc).__name__.lower()
    if status == 429 or "ratelimit" in name or "rate_limit" in name:
        return ProviderExecutionError("RATE_LIMIT", "Provider rate limit was reached", retryable=True)
    if status in {401, 403} or "auth" in name:
        return ProviderExecutionError("CREDENTIALS_MISSING", "Provider credentials were rejected", retryable=False)
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) or "timeout" in name:
        return ProviderExecutionError("TIMEOUT", "Provider request timed out", retryable=True)
    if status and int(status) >= 500:
        return ProviderExecutionError("SERVER_ERROR", "Provider service is unavailable", retryable=True)
    return ProviderExecutionError("INVALID_RESPONSE", "Provider execution returned an invalid response", retryable=True)


_PINNED_OPENAI_COMPATIBLE_TEXT = frozenset({
    "text.custom", "text.ollama", "text.lmstudio", "text.litellm",
})


def _openai_messages(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for source in payloads:
        item = dict(source)
        content = item.get("content")
        if isinstance(content, list):
            parts: list[dict[str, Any]] = []
            for part in content:
                if not isinstance(part, dict):
                    parts.append({"type": "text", "text": str(part)})
                elif part.get("type") == "image":
                    if part.get("url"):
                        parts.append({"type": "image_url", "image_url": {"url": part["url"]}})
                    elif isinstance(part.get("data"), dict) and part["data"].get("__bayanly_base64__"):
                        mime = part.get("mime_type") or "application/octet-stream"
                        parts.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{part['data']['__bayanly_base64__']}"}})
                elif part.get("type") == "text":
                    parts.append({"type": "text", "text": str(part.get("text") or "")})
            item["content"] = parts
        messages.append({key: value for key, value in item.items() if key in {"role", "content", "tool_calls", "tool_call_id", "name"}})
    return messages


async def _execute_pinned_openai_compatible(
    adapter_id: str,
    request: TextAIRequest,
    secret: str | None,
    safe_config: dict[str, Any],
) -> TextAIResult:
    from utils.outbound_http import SecureClientSession
    from utils.llm_utils import extract_structured_content

    base_url = str(safe_config.get("base_url") or "").strip().rstrip("/")
    if not base_url:
        raise ProviderExecutionError("CAPABILITY_MISMATCH", "Provider base URL is not configured", retryable=False)
    url = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
    message_payloads = request.message_payloads or [item.model_dump(mode="json") for item in request.messages]
    payload: dict[str, Any] = {
        "model": request.model or str(safe_config.get("model") or "default"),
        "messages": _openai_messages(message_payloads),
        "stream": False,
    }
    if request.max_output_tokens is not None:
        payload["max_tokens"] = request.max_output_tokens
    if request.temperature is not None:
        payload["temperature"] = request.temperature
    if request.tools_payload:
        payload["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": tool.get("name"),
                    "description": tool.get("description") or "",
                    "parameters": tool.get("schema") or tool.get("input_schema") or {"type": "object"},
                    **({"strict": bool(tool.get("strict"))} if tool.get("strict") is not None else {}),
                },
            }
            for tool in request.tools_payload
        ]
    if request.tool_choice_payload:
        mode = request.tool_choice_payload.get("mode")
        names = request.tool_choice_payload.get("tools") or []
        if len(names) == 1:
            payload["tool_choice"] = {"type": "function", "function": {"name": names[0]}}
        elif mode == "required":
            payload["tool_choice"] = "required"
        elif mode == "auto":
            payload["tool_choice"] = "auto"
    if request.response_format_payload:
        response_format = request.response_format_payload
        if response_format.get("type") == "json_schema":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_format.get("name") or "response",
                    "strict": bool(response_format.get("strict")),
                    "schema": response_format.get("json_schema") or {"type": "object"},
                },
            }
        elif response_format.get("type"):
            payload["response_format"] = {"type": response_format["type"]}
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["Authorization"] = f"Bearer {_secret_values(secret).get('api_key') or _secret_values(secret).get('value') or secret}"
    try:
        async with SecureClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=request.timeout_seconds)) as session:
            async with session.post(url, json=payload, max_response_bytes=int(os.getenv("PROVIDER_MAX_RESPONSE_BYTES", str(2 * 1024 * 1024)))) as response:
                if response.status == 429:
                    raise ProviderExecutionError("RATE_LIMIT", "Provider rate limit was reached", retryable=True)
                if response.status in {401, 403}:
                    raise ProviderExecutionError("CREDENTIALS_MISSING", "Provider credentials were rejected", retryable=False)
                if response.status >= 500:
                    raise ProviderExecutionError("SERVER_ERROR", "Provider service is unavailable", retryable=True)
                if response.status >= 400:
                    raise ProviderExecutionError("INVALID_RESPONSE", "Provider rejected the normalized request", retryable=False)
                body = await response.json()
        choice = body["choices"][0]
        message = choice["message"]
        content = message.get("content") or ""
        structured = extract_structured_content(content)
        usage = body.get("usage") or {}
        calls = [
            NormalizedToolCall(
                id=str(call.get("id") or "tool"),
                name=str((call.get("function") or {}).get("name") or "tool"),
                arguments=(call.get("function") or {}).get("arguments"),
            )
            for call in message.get("tool_calls") or []
        ]
        return TextAIResult(
            content=json.dumps(structured, ensure_ascii=False) if structured is not None else str(content),
            structured=structured,
            usage=UsageUnits(
                input_tokens=usage.get("prompt_tokens") or usage.get("input_tokens"),
                output_tokens=usage.get("completion_tokens") or usage.get("output_tokens"),
            ),
            finish_reason=choice.get("finish_reason"),
            model=str(body.get("model") or request.model or "default"),
            tool_calls=calls,
        )
    except asyncio.CancelledError:
        raise
    except ProviderExecutionError:
        raise
    except BaseException as exc:
        raise _provider_error(exc) from exc


async def execute_text_compatibility(adapter_id: str, request: TextAIRequest, secret: str | None, safe_config: dict[str, Any]) -> TextAIResult:
    if adapter_id in _PINNED_OPENAI_COMPATIBLE_TEXT:
        return await _execute_pinned_openai_compatible(adapter_id, request, secret, safe_config)
    from llmai import get_client
    from llmai.shared import JSONSchemaResponse
    from utils.llm_config import get_llm_config
    from utils.llm_utils import extract_structured_content, extract_text

    def invoke():
        with provider_environment(compatibility_environment(adapter_id, secret, safe_config)):
            client = get_client(config=get_llm_config())
            _disable_sdk_retries(client)
            messages = (
                [_legacy_message(item) for item in request.message_payloads]
                if request.message_payloads
                else [_legacy_message(item.model_dump(mode="json")) for item in request.messages]
            )
            kwargs: dict[str, Any] = {"model": request.model or "default", "messages": messages, "stream": False}
            if request.max_output_tokens is not None:
                kwargs["max_tokens"] = request.max_output_tokens
            if request.temperature is not None:
                kwargs["temperature"] = request.temperature
            if request.tools_payload:
                kwargs["tools"] = _legacy_tools(request.tools_payload)
            if request.tool_choice_payload:
                kwargs["tool_choice"] = request.tool_choice_payload
            if request.response_format_payload:
                kwargs["response_format"] = JSONSchemaResponse.model_validate(request.response_format_payload)
            response = client.generate(**kwargs)
            structured = extract_structured_content(response.content)
            content = extract_text(response.content)
            if content is None and structured is not None:
                content = json.dumps(structured, ensure_ascii=False)
            calls = [
                NormalizedToolCall(
                    id=str(getattr(call, "id", "tool")),
                    name=str(getattr(call, "name", "tool")),
                    arguments=getattr(call, "arguments", None),
                )
                for call in list(getattr(response, "tool_calls", []) or [])
            ]
            return TextAIResult(
                content=content or "",
                structured=structured,
                usage=_usage(response),
                finish_reason=getattr(response, "finish_reason", None),
                model=str(getattr(response, "model", None) or request.model or "default"),
                tool_calls=calls,
            )

    try:
        return await asyncio.to_thread(invoke)
    except asyncio.CancelledError:
        raise
    except ProviderExecutionError:
        raise
    except BaseException as exc:
        raise _provider_error(exc) from exc


async def _download_image(url: str, maximum: int) -> tuple[bytes, str]:
    from utils.outbound_http import SecureClientSession, validate_outbound_url

    await validate_outbound_url(url)
    async with SecureClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        async with session.get(url) as response:
            if response.status >= 400:
                raise ProviderExecutionError("SERVER_ERROR", "Provider image download failed", retryable=response.status >= 500)
            data = await response.content.read(maximum + 1)
            mime = (response.headers.get("Content-Type") or "image/png").split(";", 1)[0]
    if len(data) > maximum:
        raise ProviderExecutionError("INVALID_RESPONSE", "Provider image exceeds the configured size limit", retryable=False)
    return data, mime


async def execute_image_compatibility(adapter_id: str, request: ImageAIRequest, secret: str | None, safe_config: dict[str, Any]) -> ImageAIAdapterResult:
    from models.image_prompt import ImagePrompt
    from models.sql.image_asset import ImageAsset
    from services.image_generation_service import ImageGenerationService

    try:
        maximum = max(1024, min(int(os.getenv("PROVIDER_MAX_IMAGE_BYTES", str(25 * 1024 * 1024))), 100 * 1024 * 1024))
    except ValueError:
        maximum = 25 * 1024 * 1024
    outputs: list[ImageProviderOutput] = []
    try:
        with tempfile.TemporaryDirectory(prefix="bayanly-provider-image-") as output_directory:
            with provider_environment(compatibility_environment(adapter_id, secret, safe_config)):
                service = ImageGenerationService(output_directory)
                if request.style == "stock-search" and adapter_id in {"image.pexels", "image.pixabay"}:
                    finder = service.get_image_from_pexels if adapter_id == "image.pexels" else service.get_image_from_pixabay
                    found = await finder(request.prompt, limit=request.count)
                    sources = [found] if isinstance(found, str) else list(found or [])
                else:
                    sources = []
                    for _ in range(request.count):
                        value = await service.generate_image(ImagePrompt(prompt=request.prompt))
                        sources.append(value.path if isinstance(value, ImageAsset) else str(value))
                for source in sources:
                    if source.startswith(("http://", "https://")):
                        data, mime = await _download_image(source, maximum)
                        filename = os.path.basename(urlparse(source).path) or "provider-image"
                    else:
                        with open(source, "rb") as stream:
                            data = stream.read(maximum + 1)
                        if len(data) > maximum:
                            raise ProviderExecutionError("INVALID_RESPONSE", "Provider image exceeds the configured size limit", retryable=False)
                        mime = mimetypes.guess_type(source)[0] or "image/png"
                        filename = os.path.basename(source)
                    outputs.append(ImageProviderOutput(data=data, mime_type=mime, filename=filename))
    except asyncio.CancelledError:
        raise
    except ProviderExecutionError:
        raise
    except BaseException as exc:
        raise _provider_error(exc) from exc
    return ImageAIAdapterResult(
        outputs=outputs,
        usage=UsageUnits(images=len(outputs)),
        model=request.model or str(safe_config.get("model") or adapter_id.split(".", 1)[1]),
    )


async def execute_search_compatibility(adapter_id: str, request: SearchRequest, secret: str | None, safe_config: dict[str, Any]) -> SearchResult:
    from utils.web_search import search_web

    try:
        with provider_environment(compatibility_environment(adapter_id, secret, safe_config)):
            rows = await search_web(request.query, max_results=request.result_count)
    except asyncio.CancelledError:
        raise
    except ProviderExecutionError:
        raise
    except BaseException as exc:
        raise _provider_error(exc) from exc
    return SearchResult(
        items=[SearchItem(title=row.title, url=row.url, snippet=row.snippet) for row in rows],
        usage=UsageUnits(search_calls=1),
    )


async def connection_test_compatibility(adapter_id: str, family: CapabilityFamily, secret: str | None, safe_config: dict[str, Any], timeout_seconds: float) -> ProviderHealthStatus:
    try:
        async with asyncio.timeout(timeout_seconds):
            if family == CapabilityFamily.TEXT:
                await execute_text_compatibility(
                    adapter_id,
                    TextAIRequest(messages=[{"role": "user", "content": "Reply with OK."}], model=str(safe_config.get("model") or "default"), max_output_tokens=8, timeout_seconds=timeout_seconds),
                    secret,
                    safe_config,
                )
            elif family == CapabilityFamily.IMAGE:
                await execute_image_compatibility(adapter_id, ImageAIRequest(prompt="A plain validation square", width=64, height=64, timeout_seconds=timeout_seconds), secret, safe_config)
            else:
                await execute_search_compatibility(adapter_id, SearchRequest(query="Bayanly connection validation", result_count=1, timeout_seconds=timeout_seconds), secret, safe_config)
        return ProviderHealthStatus.HEALTHY
    except (TimeoutError, asyncio.TimeoutError):
        return ProviderHealthStatus.UNHEALTHY
    except Exception:
        return ProviderHealthStatus.UNHEALTHY
