from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from modules.providers.adapters.registry import PROVIDER_REGISTRY, ProviderRegistry
from modules.providers.domain.contracts import CapabilityFamily, ProviderHealthStatus, RegionPolicyStatus
from modules.providers.persistence.models import (
    ProviderAccountModel,
    ProviderCapabilityModel,
    ProviderHealthModel,
    ProviderSnapshotModel,
    RoutingPolicyModel,
)
from utils.api_errors import StableAPIError
from utils.architecture_flags import disabled_provider_adapters, policy_routing_enabled, provider_fallback_enabled


@dataclass(frozen=True)
class RoutingCandidate:
    account: ProviderAccountModel
    capability: ProviderCapabilityModel
    adapter: object
    fallback_index: int


@dataclass(frozen=True)
class RoutingPlan:
    policy: RoutingPolicyModel | None
    candidates: tuple[RoutingCandidate, ...]
    exclusions: dict[str, str]


async def plan_route(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    family: CapabilityFamily,
    model: str | None = None,
    pinned_account_id: UUID | None = None,
    region: str | None = None,
    plan: str | None = None,
    registry: ProviderRegistry = PROVIDER_REGISTRY,
) -> RoutingPlan:
    """Deterministic precedence: emergency > region > plan > health > priority > UUID."""
    policy = await session.scalar(
        select(RoutingPolicyModel).where(
            RoutingPolicyModel.workspace_id == workspace_id,
            RoutingPolicyModel.family == family,
        )
    )
    active_policy = policy if policy_routing_enabled() else None
    rows = (
        await session.execute(
            select(ProviderAccountModel, ProviderCapabilityModel)
            .join(ProviderCapabilityModel, ProviderCapabilityModel.provider_account_id == ProviderAccountModel.id)
            .where(
                ProviderAccountModel.workspace_id == workspace_id,
                ProviderCapabilityModel.workspace_id == workspace_id,
                ProviderCapabilityModel.family == family,
                ProviderCapabilityModel.enabled.is_(True),
            )
        )
    ).all()
    health_rows = list(
        (
            await session.scalars(
                select(ProviderHealthModel).where(ProviderHealthModel.workspace_id == workspace_id)
            )
        ).all()
    )
    health = {item.provider_account_id: item.status for item in health_rows}
    priority: dict[UUID, int] = {}
    for index, value in enumerate(active_policy.priority_account_ids if active_policy else []):
        try:
            priority[UUID(value)] = index
        except (TypeError, ValueError):
            # Stale policy data is ignored instead of making all routing fail.
            continue
    exclusions: dict[str, str] = {}
    disabled_adapters = disabled_provider_adapters()
    eligible = []
    for account, capability in rows:
        key = str(account.id)
        if pinned_account_id is not None and account.id != pinned_account_id:
            continue
        adapter = registry.get(account.adapter_id)
        if account.adapter_id in disabled_adapters:
            exclusions[key] = "ADAPTER_EMERGENCY_DISABLED"
        elif adapter is None or adapter.family != family:
            exclusions[key] = "ADAPTER_UNAVAILABLE"
        elif not account.enabled or account.emergency_disabled:
            exclusions[key] = "EMERGENCY_DISABLED" if account.emergency_disabled else "PROVIDER_DISABLED"
        elif account.region_policy_status == RegionPolicyStatus.BLOCKED:
            exclusions[key] = "REGION_POLICY_BLOCKED"
        elif account.region_policy_status in {RegionPolicyStatus.UNKNOWN, RegionPolicyStatus.ADMIN_REVIEW}:
            exclusions[key] = "REGION_POLICY_UNKNOWN"
        elif model and capability.model != model:
            exclusions[key] = "CAPABILITY_MISMATCH"
        elif health.get(account.id) == ProviderHealthStatus.UNHEALTHY:
            exclusions[key] = "PROVIDER_UNHEALTHY"
        elif active_policy and plan and active_policy.plan_rules.get(plan) == "BLOCKED":
            exclusions[key] = "PLAN_RESTRICTED"
        elif active_policy and region and active_policy.region_rules.get(region) == "BLOCKED":
            exclusions[key] = "REGION_POLICY_BLOCKED"
        else:
            eligible.append((account, capability, adapter))
    eligible.sort(key=lambda item: (priority.get(item[0].id, 1_000_000), item[0].adapter_id, str(item[0].id), item[1].model))
    maximum = 1
    if active_policy and active_policy.allow_fallback and provider_fallback_enabled():
        maximum += max(0, min(active_policy.max_fallbacks, 3))
    candidates = tuple(
        RoutingCandidate(account, capability, adapter, index)
        for index, (account, capability, adapter) in enumerate(eligible[:maximum])
    )
    if pinned_account_id is not None and not candidates:
        raise StableAPIError(409, "PINNED_PROVIDER_UNAVAILABLE", "Pinned provider is unavailable under current policy")
    return RoutingPlan(active_policy, candidates, exclusions)


async def persist_snapshot(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    candidate: RoutingCandidate,
    policy: RoutingPolicyModel | None,
    job_id: UUID | None,
    fallback_reason: str | None = None,
) -> ProviderSnapshotModel:
    snapshot = ProviderSnapshotModel(
        workspace_id=workspace_id,
        job_id=job_id,
        provider_account_id=candidate.account.id,
        adapter_id=candidate.account.adapter_id,
        family=candidate.capability.family,
        model=candidate.capability.model,
        routing_policy_id=policy.id if policy else None,
        routing_policy_version=policy.version if policy else 0,
        safe_config=dict(candidate.account.safe_config or {}),
        region_decision=candidate.account.region_policy_status,
        fallback_reason=fallback_reason,
    )
    session.add(snapshot)
    await session.flush()
    return snapshot
