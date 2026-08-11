"""Provider-neutral compatibility client for production text business callers.

The public shape intentionally matches the small ``llmai`` surface used by
the application. Vendor SDK construction is confined to official adapters.
"""

from __future__ import annotations

import asyncio
import base64
import contextvars
import json
import sys
import threading
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from llmai.shared import (
    AssistantToolCall,
    ResponseContent,
    ResponseStreamCompletionChunk,
    ResponseStreamContentChunk,
    ResponseUsage,
)

from api.v1.auth.context import get_current_job_id, get_current_workspace_id
from modules.providers.application.executor import ProviderExecutor
from modules.providers.domain.contracts import TextAIRequest, TextAIResult, TextMessage


@dataclass(frozen=True)
class ProviderTextClientConfig:
    operation: str = "text.generate"


def _json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"__bayanly_base64__": base64.b64encode(value).decode("ascii")}
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "value") and isinstance(getattr(value, "value"), (str, int, float, bool)):
        return value.value
    return value


def _dump(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump(mode="python", exclude_none=True, by_alias=True))
    return _json_safe(value)


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    parts.append(item["text"])
                elif item.get("type") == "image":
                    parts.append("[image attachment]")
        return "".join(parts)
    return str(content or "")


def _request_messages(payloads: list[dict[str, Any]]) -> list[TextMessage]:
    normalized: list[TextMessage] = []
    for payload in payloads:
        role = payload.get("role")
        safe_role = role if role in {"system", "user", "assistant"} else "user"
        content = _content_text(payload.get("content"))
        if not content and payload.get("tool_calls"):
            content = json.dumps(payload["tool_calls"], ensure_ascii=False, default=str)
        normalized.append(TextMessage(role=safe_role, content=content or "[empty message]"))
    return normalized


def _response_format_payload(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    payload = _dump(value)
    if not isinstance(payload, dict):
        return None
    schema = getattr(value, "json_schema", None)
    if schema is not None:
        from llmai.shared.schema import get_schema_as_dict

        payload["json_schema"] = get_schema_as_dict(schema, strict=bool(payload.get("strict")))
    return payload


def _run_on_fresh_loop(awaitable_factory):
    """Run one provider coroutine on a platform-compatible private loop.

    Text callers intentionally execute the synchronous compatibility surface in
    a worker thread.  On Windows, ``asyncio.run`` creates a Proactor loop, while
    psycopg's async driver requires a Selector loop.  Keeping the private loop
    explicit also makes its lifecycle bounded to the one normalized request.
    """

    if sys.platform != "win32":
        return asyncio.run(awaitable_factory())
    loop = asyncio.SelectorEventLoop()
    try:
        return loop.run_until_complete(awaitable_factory())
    finally:
        loop.close()


def _run_sync(awaitable_factory):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return _run_on_fresh_loop(awaitable_factory)

    state: dict[str, Any] = {}
    copied = contextvars.copy_context()

    def worker() -> None:
        try:
            state["result"] = copied.run(lambda: _run_on_fresh_loop(awaitable_factory))
        except BaseException as exc:
            state["error"] = exc

    thread = threading.Thread(target=worker, name="provider-text-client", daemon=True)
    thread.start()
    thread.join()
    if "error" in state:
        raise state["error"]
    return state["result"]


class ProviderNeutralTextClient:
    def __init__(self, config: ProviderTextClientConfig) -> None:
        self._config = config

    def generate(self, **kwargs):
        message_payloads = [_dump(message) for message in list(kwargs.get("messages") or [])]
        if not all(isinstance(item, dict) for item in message_payloads):
            raise ValueError("Provider messages must be serializable objects")
        tools_payload = [_dump(tool) for tool in list(kwargs.get("tools") or [])]
        request = TextAIRequest(
            messages=_request_messages(message_payloads),
            model=kwargs.get("model"),
            max_output_tokens=kwargs.get("max_tokens"),
            temperature=kwargs.get("temperature"),
            message_payloads=message_payloads,
            tools_payload=tools_payload,
            tool_choice_payload=_dump(kwargs.get("tool_choice")),
            response_format_payload=_response_format_payload(kwargs.get("response_format")),
            stream_requested=bool(kwargs.get("stream")),
        )

        async def invoke() -> TextAIResult:
            workspace_id = get_current_workspace_id()
            if workspace_id is None:
                raise RuntimeError("Provider execution requires an active workspace context")
            from services.database import async_session_maker

            async with async_session_maker() as session:
                return await ProviderExecutor().execute(
                    session,
                    workspace_id=workspace_id,
                    request=request,
                    job_id=get_current_job_id(),
                    operation=self._config.operation,
                )

        result = _run_sync(invoke)
        usage = ResponseUsage(
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            total_tokens=(
                (result.usage.input_tokens or 0) + (result.usage.output_tokens or 0)
                if result.usage.input_tokens is not None or result.usage.output_tokens is not None
                else None
            ),
        )
        calls = [
            AssistantToolCall(id=item.id, name=item.name, arguments=item.arguments)
            for item in result.tool_calls
        ]
        content: Any = result.structured if result.structured is not None else result.content
        if not kwargs.get("stream"):
            return ResponseContent(content=content, tool_calls=calls, usage=usage)

        def events():
            if result.content:
                yield ResponseStreamContentChunk(chunk=result.content)
            yield ResponseStreamCompletionChunk(content=content, tool_calls=calls, usage=usage)

        return events()


def get_text_client(*, config: Any):
    if isinstance(config, ProviderTextClientConfig):
        return ProviderNeutralTextClient(config)
    from llmai import get_client as get_legacy_client

    return get_legacy_client(config=config)
