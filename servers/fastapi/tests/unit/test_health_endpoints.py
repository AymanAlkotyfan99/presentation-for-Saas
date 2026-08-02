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
