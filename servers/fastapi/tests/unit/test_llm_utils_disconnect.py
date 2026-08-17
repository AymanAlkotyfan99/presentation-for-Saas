import asyncio
import json
import threading
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from llmai.shared import ResponseStreamCompletionChunk, ResponseStreamContentChunk

from utils.llm_utils import (
    StructuredGenerationError,
    generate_structured_with_schema_retries,
)


class RetryClient:
    def __init__(self):
        self.calls = []
        self.responses = [None, {"result": "ok"}]

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(content=self.responses.pop(0))


class StreamingClient:
    def __init__(self):
        self.calls = []
        self.started = threading.Event()
        self.closed = threading.Event()

    def generate(self, **kwargs):
        self.calls.append(kwargs)

        def events():
            try:
                while True:
                    self.started.set()
                    time.sleep(0.01)
                    yield ResponseStreamContentChunk(chunk='{"result":"pending"}')
            finally:
                self.closed.set()

        return events()


def test_regular_generation_keeps_existing_retry_behavior(monkeypatch):
    monkeypatch.setenv("LLM", "ollama")
    monkeypatch.setenv("PROVIDER_REGISTRY_ENABLED", "false")
    client = RetryClient()

    with patch("utils.llm_utils.asyncio.sleep", new=AsyncMock()):
        result = asyncio.run(
            generate_structured_with_schema_retries(
                client,
                "test-model",
                messages=[],
                response_format=object(),
                json_schema={},
            )
        )

    assert result == {"result": "ok"}
    assert len(client.calls) == 2
    assert all(call["stream"] is False for call in client.calls)


def test_disconnect_cancels_generation_without_retrying(monkeypatch):
    monkeypatch.setenv("LLM", "ollama")
    monkeypatch.setenv("PROVIDER_REGISTRY_ENABLED", "false")
    client = StreamingClient()

    async def run():
        async def is_disconnected():
            return client.started.is_set()

        with pytest.raises(asyncio.CancelledError):
            await generate_structured_with_schema_retries(
                client,
                "test-model",
                messages=[],
                response_format=object(),
                json_schema={},
                disconnect_checker=is_disconnected,
            )

        while not client.closed.is_set():
            await asyncio.sleep(0.001)

    asyncio.run(run())

    assert len(client.calls) == 1
    assert client.calls[0]["stream"] is True


def test_connected_request_uses_stream_completion_content(monkeypatch):
    monkeypatch.setenv("LLM", "ollama")
    monkeypatch.setenv("PROVIDER_REGISTRY_ENABLED", "false")

    class CompletedClient:
        def __init__(self):
            self.calls = []

        def generate(self, **kwargs):
            self.calls.append(kwargs)
            return iter(
                [
                    ResponseStreamCompletionChunk(
                        content={"result": "complete"}
                    )
                ]
            )

    client = CompletedClient()

    async def run():
        async def is_disconnected():
            return False

        return await generate_structured_with_schema_retries(
            client,
            "test-model",
            messages=[],
            response_format=object(),
            json_schema={},
            disconnect_checker=is_disconnected,
        )

    assert asyncio.run(run()) == {"result": "complete"}
    assert client.calls[0]["stream"] is True


def test_connected_request_keeps_schema_validation_retries(monkeypatch):
    monkeypatch.setenv("LLM", "ollama")
    monkeypatch.setenv("PROVIDER_REGISTRY_ENABLED", "false")

    class ValidationRetryClient:
        def __init__(self):
            self.calls = []
            self.responses = [{"wrong": "value"}, {"result": "fixed"}]

        def generate(self, **kwargs):
            self.calls.append(kwargs)
            return iter(
                [ResponseStreamCompletionChunk(content=self.responses.pop(0))]
            )

    client = ValidationRetryClient()

    async def run():
        async def is_disconnected():
            return False

        return await generate_structured_with_schema_retries(
            client,
            "test-model",
            messages=[],
            response_format=object(),
            json_schema={
                "type": "object",
                "properties": {"result": {"type": "string"}},
                "required": ["result"],
            },
            validate_schema=True,
            disconnect_checker=is_disconnected,
        )

    assert asyncio.run(run()) == {"result": "fixed"}
    assert len(client.calls) == 2
    assert all(call["stream"] is True for call in client.calls)


def test_registry_mode_rejects_invalid_schema_after_one_correction(monkeypatch):
    monkeypatch.setenv("PROVIDER_REGISTRY_ENABLED", "true")

    class BoundedClient:
        def __init__(self):
            self.calls = []
            self.responses = [{"wrong": "value"}, {"still": "wrong"}, {"result": "late"}]

        def generate(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(content=self.responses.pop(0))

    client = BoundedClient()
    with pytest.raises(StructuredGenerationError):
        asyncio.run(
            generate_structured_with_schema_retries(
                client,
                "test-model",
                messages=[],
                response_format=object(),
                json_schema={
                    "type": "object",
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                },
                validate_schema=True,
                validate_schema_max_loop_count=99,
            )
        )

    assert len(client.calls) == 2


def _raise_wrapped_json_error(raw_response: str) -> None:
    try:
        json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise RuntimeError("provider structured response parsing failed") from exc


def test_registry_mode_corrects_a_malformed_first_response(monkeypatch):
    monkeypatch.setenv("PROVIDER_REGISTRY_ENABLED", "true")

    class MalformedThenCorrectedClient:
        def __init__(self):
            self.calls = []

        def generate(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                _raise_wrapped_json_error('{\n  "slides": [0, 1, 2\n}')
            return SimpleNamespace(content={"slides": [0, 1, 2]})

    client = MalformedThenCorrectedClient()
    result = asyncio.run(
        generate_structured_with_schema_retries(
            client,
            "test-model",
            messages=[],
            response_format=object(),
            json_schema={
                "type": "object",
                "properties": {
                    "slides": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 3,
                        "maxItems": 3,
                    }
                },
                "required": ["slides"],
            },
            validate_schema=True,
        )
    )

    assert result == {"slides": [0, 1, 2]}
    assert len(client.calls) == 2
    correction_message = str(client.calls[1]["messages"][-1].content)
    assert "not valid JSON" in correction_message
    assert "Return corrected JSON only" in correction_message


def test_legacy_mode_corrects_a_malformed_first_response(monkeypatch):
    monkeypatch.setenv("LLM", "openrouter")
    monkeypatch.setenv("PROVIDER_REGISTRY_ENABLED", "false")

    class MalformedThenCorrectedClient:
        def __init__(self):
            self.calls = []

        def generate(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                _raise_wrapped_json_error('{\n  "slides": [0, 1, 2\n}')
            return SimpleNamespace(content={"slides": [0, 1, 2]})

    client = MalformedThenCorrectedClient()
    with patch("utils.llm_utils.asyncio.sleep", new=AsyncMock()):
        result = asyncio.run(
            generate_structured_with_schema_retries(
                client,
                "test-model",
                messages=[],
                response_format=object(),
                json_schema={
                    "type": "object",
                    "properties": {
                        "slides": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "minItems": 3,
                            "maxItems": 3,
                        }
                    },
                    "required": ["slides"],
                },
                validate_schema=True,
            )
        )

    assert result == {"slides": [0, 1, 2]}
    assert len(client.calls) == 2
    correction_message = str(client.calls[1]["messages"][-1].content)
    assert "not valid JSON" in correction_message


def test_legacy_mode_exhausts_three_parse_attempts_safely(monkeypatch, caplog):
    monkeypatch.setenv("LLM", "openrouter")
    monkeypatch.setenv("PROVIDER_REGISTRY_ENABLED", "false")
    malformed_response = '{\n  "slides": [0, 1, 2\n}'

    class AlwaysMalformedClient:
        def __init__(self):
            self.calls = []

        def generate(self, **kwargs):
            self.calls.append(kwargs)
            _raise_wrapped_json_error(malformed_response)

    client = AlwaysMalformedClient()
    with patch("utils.llm_utils.asyncio.sleep", new=AsyncMock()):
        with pytest.raises(StructuredGenerationError) as exc_info:
            asyncio.run(
                generate_structured_with_schema_retries(
                    client,
                    "test-model",
                    messages=[],
                    response_format=object(),
                    json_schema={"type": "object"},
                    validate_schema=True,
                )
            )

    assert len(client.calls) == 3
    assert malformed_response not in str(exc_info.value)
    assert malformed_response not in caplog.text


@pytest.mark.parametrize(
    "malformed_response",
    [
        '{\n  "slides": [0, 1, 2\n}',
        '{\n  "slides": {"first": 0]\n}',
    ],
)
def test_registry_mode_exhausts_two_attempts_without_exposing_raw_json(
    monkeypatch,
    caplog,
    malformed_response,
):
    monkeypatch.setenv("PROVIDER_REGISTRY_ENABLED", "true")

    class AlwaysMalformedClient:
        def __init__(self):
            self.calls = []

        def generate(self, **kwargs):
            self.calls.append(kwargs)
            _raise_wrapped_json_error(malformed_response)

    client = AlwaysMalformedClient()
    with pytest.raises(StructuredGenerationError) as exc_info:
        asyncio.run(
            generate_structured_with_schema_retries(
                client,
                "test-model",
                messages=[],
                response_format=object(),
                json_schema={"type": "object"},
                validate_schema=True,
                validate_schema_max_loop_count=99,
            )
        )

    assert len(client.calls) == 2
    assert malformed_response not in str(exc_info.value)
    assert malformed_response not in caplog.text
