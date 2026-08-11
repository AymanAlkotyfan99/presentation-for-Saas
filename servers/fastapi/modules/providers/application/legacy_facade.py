"""Controlled compatibility boundary for business services during rollout.

Business modules import this provider-facing facade instead of the legacy
provider switch module directly. The registry path can replace its internals
behind feature flags without another cross-repository import migration.
"""

from __future__ import annotations

from typing import Any

from utils.architecture_flags import legacy_provider_switches_enabled
from modules.providers.application.runtime import provider_platform_active
from modules.providers.application.text_client import ProviderTextClientConfig


def get_text_provider_client_config(
    *, use_openai_responses_api: bool = False, operation: str = "text.generate",
) -> Any:
    if provider_platform_active():
        return ProviderTextClientConfig(operation=operation)
    if not legacy_provider_switches_enabled():
        raise RuntimeError("Legacy provider switches are disabled")
    from utils.llm_config import get_llm_config

    return get_llm_config(use_openai_responses_api=use_openai_responses_api)
