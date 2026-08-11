"""Authoritative provider-platform rollout guardrails."""

from __future__ import annotations

from utils.architecture_flags import (
    encrypted_provider_config_enabled,
    policy_routing_enabled,
    provider_registry_enabled,
)


def provider_platform_active() -> bool:
    """Return whether execution must use Sprint 10, failing closed on partial rollout."""

    if not provider_registry_enabled():
        return False
    missing: list[str] = []
    if not encrypted_provider_config_enabled():
        missing.append("ENCRYPTED_PROVIDER_CONFIG_ENABLED")
    if not policy_routing_enabled():
        missing.append("POLICY_ROUTING_ENABLED")
    if missing:
        raise RuntimeError(
            "Provider registry rollout is incomplete; required flags are disabled: "
            + ", ".join(missing)
        )
    return True
