from unittest.mock import AsyncMock

import pytest

from api import main


@pytest.mark.anyio
async def test_liveness_is_process_local() -> None:
    assert await main.liveness() == {"status": "live"}


@pytest.mark.anyio
async def test_readiness_fails_closed_when_operation_backend_is_unhealthy(
    monkeypatch,
) -> None:
    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        execute = AsyncMock(return_value=1)

    monkeypatch.setattr(main, "async_session_maker", lambda: Session())
    monkeypatch.setattr(
        main,
        "healthcheck_operation_controls",
        AsyncMock(return_value=False),
    )

    response = await main.readiness()
    assert response.status_code == 503
    assert b'"operation_controls":false' in response.body


@pytest.mark.anyio
async def test_readiness_checks_enabled_job_and_storage_dependencies(
    monkeypatch,
) -> None:
    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        execute = AsyncMock(return_value=1)

    class Transport:
        async def health(self):
            return True

        async def close(self):
            return None

    class Storage:
        async def health(self):
            return True

    monkeypatch.setattr(main, "async_session_maker", lambda: Session())
    monkeypatch.setattr(
        main,
        "healthcheck_operation_controls",
        AsyncMock(return_value=True),
    )
    monkeypatch.setenv("DURABLE_JOBS_ENABLED", "true")
    monkeypatch.setenv("OBJECT_STORAGE_WRITES_ENABLED", "true")
    from modules.assets.providers import storage
    from modules.jobs import outbox

    monkeypatch.setattr(outbox.RedisQueueTransport, "from_environment", lambda: Transport())
    monkeypatch.setattr(storage, "get_storage_provider", lambda: Storage())

    response = await main.readiness()
    assert response.status_code == 200
    assert b'"job_redis":true' in response.body
    assert b'"object_storage":true' in response.body
