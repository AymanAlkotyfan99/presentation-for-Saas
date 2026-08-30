import asyncio
from unittest.mock import patch

from api.runtime_capabilities import runtime_capabilities


def test_runtime_capabilities_use_authoritative_architecture_flags():
    with patch("api.runtime_capabilities.workspaces_enabled", return_value=False), patch(
        "api.runtime_capabilities.provider_registry_enabled", return_value=True
    ):
        result = asyncio.run(runtime_capabilities())

    assert result == {"workspaces": False, "providerRegistry": True}
