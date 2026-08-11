"""Provider account configuration and policy validation.

Only non-secret configuration is stored on provider accounts. Credentials are
always written through the envelope service in ``security.secrets``.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from modules.providers.adapters.registry import PROVIDER_REGISTRY, ProviderRegistry
from modules.providers.domain.contracts import CapabilityFamily, RegionPolicyStatus
from modules.providers.persistence.models import (
    ProviderAccountModel,
    ProviderCapabilityModel,
    ProviderHealthModel,
    RoutingPolicyModel,
)
from modules.workspaces.application.audit import append_audit_event
from utils.api_errors import StableAPIError
from utils.outbound_http import OutboundSecurityError, validate_outbound_url


MAX_SAFE_CONFIG_FIELDS = 32
FORBIDDEN_CONFIG_FRAGMENTS = ("key", "secret", "token", "password", "authorization", "cookie")
ENDPOINT_FIELDS = frozenset({"base_url", "baseUrl", "endpoint", "url"})


async def validate_safe_config(value: dict) -> dict:
    if len(value) > MAX_SAFE_CONFIG_FIELDS:
        raise StableAPIError(422, "PROVIDER_CONFIG_TOO_LARGE", "Provider configuration has too many fields")
    clean: dict = {}
    for key, item in value.items():
        name = str(key)[:64]
        normalized = name.lower().replace("-", "_")
        if any(fragment in normalized for fragment in FORBIDDEN_CONFIG_FRAGMENTS):
            raise StableAPIError(422, "PROVIDER_SECRET_IN_CONFIG", "Secrets must use the encrypted secret endpoint")
        if not isinstance(item, (str, int, float, bool, type(None))):
            raise StableAPIError(422, "PROVIDER_CONFIG_INVALID", "Provider configuration values must be scalar")
        if isinstance(item, str) and len(item) > 2048:
            raise StableAPIError(422, "PROVIDER_CONFIG_TOO_LARGE", "Provider configuration value is too large")
        if name in ENDPOINT_FIELDS and item:
            try:
                await validate_outbound_url(str(item))
            except OutboundSecurityError as exc:
                raise StableAPIError(422, "PROVIDER_ENDPOINT_BLOCKED", "Provider endpoint is not permitted") from exc
        clean[name] = item
    return clean


async def create_provider_account(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    actor_id: UUID | None,
    adapter_id: str,
    name: str,
    default_model: str | None,
    safe_config: dict,
    region_policy_status: RegionPolicyStatus,
    capability_models: list[str],
    registry: ProviderRegistry = PROVIDER_REGISTRY,
) -> ProviderAccountModel:
    adapter = registry.get(adapter_id)
    if adapter is None:
        raise StableAPIError(422, "PROVIDER_ADAPTER_UNKNOWN", "Provider adapter is not registered")
    config = await validate_safe_config(safe_config)
    models = list(dict.fromkeys(model.strip() for model in capability_models if model.strip()))
    if not models:
        models = [default_model or "default"]
    if len(models) > 100 or any(len(model) > 160 for model in models):
        raise StableAPIError(422, "PROVIDER_CAPABILITY_INVALID", "Provider capability list is invalid")
    account = ProviderAccountModel(
        workspace_id=workspace_id,
        owner_id=actor_id,
        adapter_id=adapter_id,
        name=name.strip(),
        default_model=default_model,
        safe_config=config,
        region_policy_status=region_policy_status,
    )
    session.add(account)
    await session.flush()
    for model in models:
        session.add(ProviderCapabilityModel(
            provider_account_id=account.id,
            workspace_id=workspace_id,
            family=adapter.family,
            model=model,
            metadata_json=dict(adapter.safe_metadata),
        ))
    session.add(ProviderHealthModel(provider_account_id=account.id, workspace_id=workspace_id))
    append_audit_event(
        session, workspace_id=workspace_id, actor_id=actor_id,
        event_type="provider.account.created", subject_type="provider_account", subject_id=account.id,
    )
    await session.flush()
    return account


async def update_routing_policy(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    actor_id: UUID | None,
    family: CapabilityFamily,
    priority_account_ids: list[UUID],
    allow_fallback: bool,
    max_fallbacks: int,
    region_rules: dict[str, str],
    plan_rules: dict[str, str],
) -> RoutingPolicyModel:
    if max_fallbacks < 0 or max_fallbacks > 3:
        raise StableAPIError(422, "PROVIDER_FALLBACK_INVALID", "Provider fallback count must be between zero and three")
    if not allow_fallback and max_fallbacks:
        raise StableAPIError(422, "PROVIDER_FALLBACK_INVALID", "Fallback count requires fallback to be enabled")
    identifiers = list(dict.fromkeys(priority_account_ids))
    accounts = list((await session.scalars(select(ProviderAccountModel).where(
        ProviderAccountModel.workspace_id == workspace_id,
        ProviderAccountModel.id.in_(identifiers),
    ))).all()) if identifiers else []
    if len(accounts) != len(identifiers):
        raise StableAPIError(422, "PROVIDER_POLICY_ACCOUNT_INVALID", "Routing policy references an unavailable account")
    row = await session.scalar(select(RoutingPolicyModel).where(
        RoutingPolicyModel.workspace_id == workspace_id,
        RoutingPolicyModel.family == family,
    ).with_for_update())
    if row is None:
        row = RoutingPolicyModel(workspace_id=workspace_id, family=family)
        session.add(row)
    else:
        row.version += 1
    row.priority_account_ids = [str(value) for value in identifiers]
    row.allow_fallback = allow_fallback
    row.max_fallbacks = max_fallbacks
    row.region_rules = dict(region_rules)
    row.plan_rules = dict(plan_rules)
    row.updated_by = actor_id
    append_audit_event(
        session, workspace_id=workspace_id, actor_id=actor_id,
        event_type="provider.policy.updated", subject_type="routing_policy", subject_id=row.id,
        metadata={"enabled": allow_fallback},
    )
    await session.flush()
    return row
