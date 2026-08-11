"""Workspace-scoped provider registry, credentials, policy, and health API."""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from api.v1.auth.principal import principal_from_request
from modules.jobs.application.submit import JobSubmission, submit_job
from modules.jobs.domain.models import QueueClass
from modules.providers.adapters.registry import PROVIDER_REGISTRY
from modules.providers.application.configuration import create_provider_account, update_routing_policy, validate_safe_config
from modules.providers.domain.contracts import CapabilityFamily, RegionPolicyStatus
from modules.providers.domain.routing import plan_route
from modules.providers.persistence.models import (
    EncryptedProviderSecretModel,
    ProviderAccountModel,
    ProviderCapabilityModel,
    ProviderHealthModel,
    RoutingPolicyModel,
)
from modules.providers.security.secrets import delete_provider_secret, rotate_provider_secret
from modules.workspaces.application.audit import append_audit_event
from modules.workspaces.application.authorization import authorize_workspace
from modules.workspaces.domain.models import Permission
from services.database import get_async_session
from utils.api_errors import StableAPIError
from utils.architecture_flags import durable_jobs_enabled, encrypted_provider_config_enabled, provider_registry_enabled


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda value: "".join([value.split("_")[0]] + [part.title() for part in value.split("_")[1:]]),
        populate_by_name=True, extra="forbid",
    )


class AccountCreate(CamelModel):
    adapter_id: str = Field(min_length=3, max_length=128)
    name: str = Field(min_length=1, max_length=160)
    default_model: str | None = Field(default=None, max_length=160)
    capability_models: list[str] = Field(default_factory=list, max_length=100)
    safe_config: dict = Field(default_factory=dict)
    region_policy_status: RegionPolicyStatus = RegionPolicyStatus.UNKNOWN
    secret: str | None = Field(default=None, min_length=1, max_length=16_384, repr=False)


class AccountUpdate(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    default_model: str | None = Field(default=None, max_length=160)
    capability_models: list[str] | None = Field(default=None, max_length=100)
    safe_config: dict | None = None
    region_policy_status: RegionPolicyStatus | None = None
    enabled: bool | None = None
    emergency_disabled: bool | None = None


class SecretRotate(CamelModel):
    secret: str = Field(min_length=1, max_length=16_384, repr=False)


class PolicyUpdate(CamelModel):
    priority_account_ids: list[UUID] = Field(default_factory=list, max_length=100)
    allow_fallback: bool = False
    max_fallbacks: int = Field(default=0, ge=0, le=3)
    region_rules: dict[str, str] = Field(default_factory=dict)
    plan_rules: dict[str, str] = Field(default_factory=dict)


class PolicySimulation(CamelModel):
    family: CapabilityFamily
    model: str | None = Field(default=None, max_length=160)
    pinned_account_id: UUID | None = None
    region: str | None = Field(default=None, max_length=32)
    plan: str | None = Field(default=None, max_length=64)


class EnabledUpdate(CamelModel):
    enabled: bool


def _require_enabled() -> None:
    if not provider_registry_enabled():
        raise StableAPIError(404, "PROVIDER_REGISTRY_DISABLED", "Provider registry is not enabled")


PROVIDERS_ROUTER = APIRouter(prefix="/api/v1/providers", tags=["Providers"], dependencies=[Depends(_require_enabled)])


async def _authorize_current(request: Request, session: AsyncSession, permission: Permission):
    principal = principal_from_request(request)
    if principal.workspace_id is None:
        raise StableAPIError(409, "WORKSPACE_CONTEXT_REQUIRED", "Current workspace is unavailable")
    await authorize_workspace(session, principal=principal, workspace_id=principal.workspace_id, permission=permission)
    return principal


async def _account(session: AsyncSession, request: Request, account_id: UUID, permission: Permission, *, lock=False):
    statement = select(ProviderAccountModel).where(ProviderAccountModel.id == account_id)
    if lock:
        statement = statement.with_for_update()
    account = await session.scalar(statement)
    if account is None:
        raise StableAPIError(404, "PROVIDER_ACCOUNT_NOT_FOUND", "Provider account not found")
    principal = principal_from_request(request)
    await authorize_workspace(session, principal=principal, workspace_id=account.workspace_id, permission=permission, resource_workspace_id=account.workspace_id)
    return account, principal


def _account_json(account, capabilities, health, has_secret: bool):
    return {
        "id": str(account.id), "adapterId": account.adapter_id, "name": account.name,
        "defaultModel": account.default_model, "safeConfig": account.safe_config,
        "regionPolicyStatus": account.region_policy_status.value, "enabled": account.enabled,
        "emergencyDisabled": account.emergency_disabled, "hasSecret": has_secret,
        "maskedSecret": "••••••••" if has_secret else None,
        "capabilities": [{"id": str(item.id), "family": item.family.value, "model": item.model, "enabled": item.enabled, "metadata": item.metadata_json} for item in capabilities],
        "health": {"status": health.status.value, "latencyMs": health.latency_ms, "safeErrorCode": health.safe_error_code, "checkedAt": health.checked_at} if health else None,
    }


async def _serialize_account(session: AsyncSession, account: ProviderAccountModel):
    capabilities = list((await session.scalars(select(ProviderCapabilityModel).where(ProviderCapabilityModel.provider_account_id == account.id))).all())
    health = await session.scalar(select(ProviderHealthModel).where(ProviderHealthModel.provider_account_id == account.id))
    has_secret = (await session.scalar(select(EncryptedProviderSecretModel.id).where(
        EncryptedProviderSecretModel.provider_account_id == account.id,
        EncryptedProviderSecretModel.deleted_at.is_(None),
    ).limit(1))) is not None
    return _account_json(account, capabilities, health, has_secret)


@PROVIDERS_ROUTER.get("/adapters")
async def adapters(request: Request, session: AsyncSession = Depends(get_async_session)):
    await _authorize_current(request, session, Permission.WORKSPACE_VIEW)
    return [{"adapterId": item.adapter_id, "family": item.family.value, "models": item.models, "metadata": item.safe_metadata} for item in PROVIDER_REGISTRY.list()]


@PROVIDERS_ROUTER.get("/accounts")
async def list_accounts(request: Request, session: AsyncSession = Depends(get_async_session)):
    principal = await _authorize_current(request, session, Permission.WORKSPACE_VIEW)
    accounts = list((await session.scalars(select(ProviderAccountModel).where(ProviderAccountModel.workspace_id == principal.workspace_id).order_by(ProviderAccountModel.name))).all())
    return [await _serialize_account(session, item) for item in accounts]


@PROVIDERS_ROUTER.get("/capabilities")
async def capabilities(request: Request, family: CapabilityFamily | None = None, session: AsyncSession = Depends(get_async_session)):
    principal = await _authorize_current(request, session, Permission.WORKSPACE_VIEW)
    statement = select(ProviderCapabilityModel).where(ProviderCapabilityModel.workspace_id == principal.workspace_id)
    if family is not None:
        statement = statement.where(ProviderCapabilityModel.family == family)
    rows = list((await session.scalars(statement.order_by(ProviderCapabilityModel.family, ProviderCapabilityModel.model))).all())
    return [{"id": str(item.id), "accountId": str(item.provider_account_id), "family": item.family.value, "model": item.model, "enabled": item.enabled, "metadata": item.metadata_json} for item in rows]


@PROVIDERS_ROUTER.get("/health")
async def health(request: Request, session: AsyncSession = Depends(get_async_session)):
    principal = await _authorize_current(request, session, Permission.WORKSPACE_VIEW)
    rows = list((await session.scalars(select(ProviderHealthModel).where(ProviderHealthModel.workspace_id == principal.workspace_id))).all())
    return [{"accountId": str(item.provider_account_id), "status": item.status.value, "latencyMs": item.latency_ms, "safeErrorCode": item.safe_error_code, "checkedAt": item.checked_at} for item in rows]


@PROVIDERS_ROUTER.post("/accounts", status_code=201)
async def create_account(payload: AccountCreate, request: Request, session: AsyncSession = Depends(get_async_session)):
    principal = await _authorize_current(request, session, Permission.CREDENTIALS_MANAGE)
    account = await create_provider_account(
        session, workspace_id=principal.workspace_id, actor_id=principal.user_id,
        adapter_id=payload.adapter_id, name=payload.name, default_model=payload.default_model,
        safe_config=payload.safe_config, region_policy_status=payload.region_policy_status,
        capability_models=payload.capability_models,
    )
    if payload.secret is not None:
        if not encrypted_provider_config_enabled():
            raise StableAPIError(409, "ENCRYPTED_PROVIDER_CONFIG_DISABLED", "Encrypted provider configuration is not enabled")
        await rotate_provider_secret(session, account_id=account.id, workspace_id=account.workspace_id, name="api_key", plaintext=payload.secret)
        append_audit_event(session, workspace_id=account.workspace_id, actor_id=principal.user_id, event_type="provider.secret.created", subject_type="provider_account", subject_id=account.id)
    await session.commit()
    return await _serialize_account(session, account)


@PROVIDERS_ROUTER.patch("/accounts/{account_id}")
async def update_account(account_id: UUID, payload: AccountUpdate, request: Request, session: AsyncSession = Depends(get_async_session)):
    account, principal = await _account(session, request, account_id, Permission.CREDENTIALS_MANAGE, lock=True)
    if payload.name is not None: account.name = payload.name.strip()
    if payload.default_model is not None: account.default_model = payload.default_model.strip()
    if payload.safe_config is not None: account.safe_config = await validate_safe_config(payload.safe_config)
    if payload.region_policy_status is not None: account.region_policy_status = payload.region_policy_status
    if payload.enabled is not None: account.enabled = payload.enabled
    if payload.emergency_disabled is not None: account.emergency_disabled = payload.emergency_disabled
    if payload.capability_models is not None:
        desired = list(dict.fromkeys(value.strip() for value in payload.capability_models if value.strip()))
        if not desired or any(len(value) > 160 for value in desired):
            raise StableAPIError(422, "PROVIDER_CAPABILITY_INVALID", "At least one valid capability model is required")
        if account.default_model and account.default_model not in desired:
            raise StableAPIError(422, "PROVIDER_DEFAULT_MODEL_INVALID", "Default model must be an enabled capability")
        adapter = PROVIDER_REGISTRY.get(account.adapter_id)
        if adapter is None:
            raise StableAPIError(409, "PROVIDER_ADAPTER_UNAVAILABLE", "Provider adapter is unavailable")
        capabilities = list((await session.scalars(select(ProviderCapabilityModel).where(
            ProviderCapabilityModel.provider_account_id == account.id,
            ProviderCapabilityModel.workspace_id == account.workspace_id,
        ).with_for_update())).all())
        by_model = {item.model: item for item in capabilities}
        for item in capabilities:
            item.enabled = item.model in desired
        for model in desired:
            if model not in by_model:
                session.add(ProviderCapabilityModel(
                    provider_account_id=account.id,
                    workspace_id=account.workspace_id,
                    family=adapter.family,
                    model=model,
                    metadata_json=dict(adapter.safe_metadata),
                ))
    elif payload.default_model is not None:
        capability = await session.scalar(select(ProviderCapabilityModel).where(
            ProviderCapabilityModel.provider_account_id == account.id,
            ProviderCapabilityModel.workspace_id == account.workspace_id,
            ProviderCapabilityModel.model == account.default_model,
        ).with_for_update())
        if capability is None:
            adapter = PROVIDER_REGISTRY.get(account.adapter_id)
            if adapter is None:
                raise StableAPIError(409, "PROVIDER_ADAPTER_UNAVAILABLE", "Provider adapter is unavailable")
            session.add(ProviderCapabilityModel(
                provider_account_id=account.id,
                workspace_id=account.workspace_id,
                family=adapter.family,
                model=account.default_model,
                metadata_json=dict(adapter.safe_metadata),
            ))
        else:
            capability.enabled = True
    append_audit_event(session, workspace_id=account.workspace_id, actor_id=principal.user_id, event_type="provider.account.updated", subject_type="provider_account", subject_id=account.id, metadata={"enabled": account.enabled})
    await session.commit()
    return await _serialize_account(session, account)


@PROVIDERS_ROUTER.put("/accounts/{account_id}/secret", status_code=204)
async def rotate_secret(account_id: UUID, payload: SecretRotate, request: Request, session: AsyncSession = Depends(get_async_session)):
    if not encrypted_provider_config_enabled():
        raise StableAPIError(409, "ENCRYPTED_PROVIDER_CONFIG_DISABLED", "Encrypted provider configuration is not enabled")
    account, principal = await _account(session, request, account_id, Permission.CREDENTIALS_MANAGE, lock=True)
    await rotate_provider_secret(session, account_id=account.id, workspace_id=account.workspace_id, name="api_key", plaintext=payload.secret)
    append_audit_event(session, workspace_id=account.workspace_id, actor_id=principal.user_id, event_type="provider.secret.rotated", subject_type="provider_account", subject_id=account.id)
    await session.commit()


@PROVIDERS_ROUTER.delete("/accounts/{account_id}/secret", status_code=204)
async def delete_secret(account_id: UUID, request: Request, session: AsyncSession = Depends(get_async_session)):
    account, principal = await _account(session, request, account_id, Permission.CREDENTIALS_MANAGE, lock=True)
    await delete_provider_secret(session, account_id=account.id)
    append_audit_event(session, workspace_id=account.workspace_id, actor_id=principal.user_id, event_type="provider.secret.deleted", subject_type="provider_account", subject_id=account.id)
    await session.commit()


@PROVIDERS_ROUTER.post("/accounts/{account_id}/connection-tests", status_code=202)
async def connection_test(account_id: UUID, request: Request, session: AsyncSession = Depends(get_async_session)):
    if not durable_jobs_enabled():
        raise StableAPIError(409, "DURABLE_JOBS_DISABLED", "Durable jobs are required for provider connection tests")
    account, principal = await _account(session, request, account_id, Permission.CREDENTIALS_MANAGE)
    job, replay = await submit_job(session, JobSubmission(
        operation="provider.connection_test", queue_class=QueueClass.MAINTENANCE,
        workspace_id=account.workspace_id, actor_id=principal.user_id,
        actor_service_account_id=principal.service_account_id,
        idempotency_scope=f"provider:{account.id}:connection-test",
        idempotency_key=request.headers.get("Idempotency-Key") or str(uuid4()),
        payload={"provider_account_id": str(account.id)}, max_attempts=2,
        resource_type="provider_account", resource_id=str(account.id),
    ))
    await session.commit()
    return {"jobId": str(job.id), "replayed": replay}


@PROVIDERS_ROUTER.put("/accounts/{account_id}/emergency-disable")
async def emergency_disable(account_id: UUID, payload: EnabledUpdate, request: Request, session: AsyncSession = Depends(get_async_session)):
    account, principal = await _account(session, request, account_id, Permission.CREDENTIALS_MANAGE, lock=True)
    account.emergency_disabled = payload.enabled
    append_audit_event(session, workspace_id=account.workspace_id, actor_id=principal.user_id, event_type="provider.emergency.updated", subject_type="provider_account", subject_id=account.id, metadata={"enabled": payload.enabled})
    await session.commit()
    return await _serialize_account(session, account)


@PROVIDERS_ROUTER.put("/accounts/{account_id}/capabilities/{capability_id}")
async def update_capability(account_id: UUID, capability_id: UUID, payload: EnabledUpdate, request: Request, session: AsyncSession = Depends(get_async_session)):
    account, principal = await _account(session, request, account_id, Permission.CREDENTIALS_MANAGE)
    capability = await session.scalar(select(ProviderCapabilityModel).where(
        ProviderCapabilityModel.id == capability_id,
        ProviderCapabilityModel.provider_account_id == account.id,
        ProviderCapabilityModel.workspace_id == account.workspace_id,
    ).with_for_update())
    if capability is None:
        raise StableAPIError(404, "PROVIDER_CAPABILITY_NOT_FOUND", "Provider capability not found")
    capability.enabled = payload.enabled
    append_audit_event(session, workspace_id=account.workspace_id, actor_id=principal.user_id, event_type="provider.capability.updated", subject_type="provider_capability", subject_id=capability.id, metadata={"enabled": payload.enabled})
    await session.commit()
    return {"id": str(capability.id), "enabled": capability.enabled}


@PROVIDERS_ROUTER.get("/routing-policies/{family}")
async def get_policy(family: CapabilityFamily, request: Request, session: AsyncSession = Depends(get_async_session)):
    principal = await _authorize_current(request, session, Permission.WORKSPACE_VIEW)
    return await session.scalar(select(RoutingPolicyModel).where(RoutingPolicyModel.workspace_id == principal.workspace_id, RoutingPolicyModel.family == family))


@PROVIDERS_ROUTER.put("/routing-policies/{family}")
async def put_policy(family: CapabilityFamily, payload: PolicyUpdate, request: Request, session: AsyncSession = Depends(get_async_session)):
    principal = await _authorize_current(request, session, Permission.CREDENTIALS_MANAGE)
    policy = await update_routing_policy(
        session, workspace_id=principal.workspace_id, actor_id=principal.user_id, family=family,
        priority_account_ids=payload.priority_account_ids, allow_fallback=payload.allow_fallback,
        max_fallbacks=payload.max_fallbacks, region_rules=payload.region_rules, plan_rules=payload.plan_rules,
    )
    await session.commit()
    return policy


@PROVIDERS_ROUTER.post("/routing-policies/simulate")
async def simulate_policy(payload: PolicySimulation, request: Request, session: AsyncSession = Depends(get_async_session)):
    principal = await _authorize_current(request, session, Permission.WORKSPACE_VIEW)
    planned = await plan_route(session, workspace_id=principal.workspace_id, family=payload.family, model=payload.model, pinned_account_id=payload.pinned_account_id, region=payload.region, plan=payload.plan)
    return {"candidates": [{"accountId": str(item.account.id), "adapterId": item.account.adapter_id, "model": item.capability.model, "fallbackIndex": item.fallback_index} for item in planned.candidates], "exclusions": planned.exclusions, "policyVersion": planned.policy.version if planned.policy else 0}
