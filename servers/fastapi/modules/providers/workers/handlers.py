from __future__ import annotations

import asyncio
from time import monotonic
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlmodel import select

from modules.jobs.domain.models import QueueClass, RetryClass
from modules.jobs.workers.registry import JobRegistry, OperationDefinition
from modules.jobs.workers.runtime import JobExecutionContext, JobHandlerError
from modules.workspaces.domain.models import Permission
from modules.providers.adapters.registry import PROVIDER_REGISTRY
from modules.providers.domain.contracts import ProviderHealthStatus
from modules.providers.persistence.models import ProviderAccountModel, ProviderHealthModel
from modules.providers.security.secrets import SecretDecryptionError, resolve_provider_secret
from utils.datetime_utils import get_current_utc_datetime


class ProviderConnectionTestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_account_id: UUID


async def test_provider_connection(context: JobExecutionContext, payload: ProviderConnectionTestPayload) -> dict:
    async with context.worker.session_factory() as session:
        account = await session.scalar(
            select(ProviderAccountModel)
            .where(ProviderAccountModel.id == payload.provider_account_id)
            .execution_options(skip_workspace_scope=True, skip_owner_scope=True)
        )
        if account is None or account.workspace_id != context.claim.workspace_id:
            raise JobHandlerError(RetryClass.NON_RETRYABLE_AUTHORIZATION, "PROVIDER_ACCOUNT_NOT_FOUND", "Provider account was not found")
        adapter = PROVIDER_REGISTRY.get(account.adapter_id)
        if adapter is None or not account.enabled or account.emergency_disabled:
            raise JobHandlerError(RetryClass.NON_RETRYABLE_VALIDATION, "PROVIDER_DISABLED", "Provider account is unavailable")
        try:
            secret = await resolve_provider_secret(session, account_id=account.id)
        except SecretDecryptionError as exc:
            raise JobHandlerError(RetryClass.NON_RETRYABLE_AUTHORIZATION, "PROVIDER_CREDENTIALS_UNAVAILABLE", "Provider credentials are unavailable") from exc
        safe_config = dict(account.safe_config)
        if account.default_model and "model" not in safe_config:
            safe_config["model"] = account.default_model
        account_id = account.id
    started = monotonic()
    safe_error_code: str | None = None
    try:
        async with asyncio.timeout(20):
            status = await adapter.connection_test(secret=secret, safe_config=safe_config, timeout_seconds=20)
    except TimeoutError:
        status = ProviderHealthStatus.UNHEALTHY
        safe_error_code = "PROVIDER_TIMEOUT"
    except Exception:
        status = ProviderHealthStatus.UNHEALTHY
        safe_error_code = "PROVIDER_CONNECTION_FAILED"
    finally:
        secret = None
    latency_ms = min(int((monotonic() - started) * 1000), 2_147_483_647)
    async with context.worker.session_factory() as session:
        health = await session.scalar(select(ProviderHealthModel).where(
            ProviderHealthModel.provider_account_id == account_id,
        ).with_for_update())
        if health is None:
            health = ProviderHealthModel(provider_account_id=account_id, workspace_id=context.claim.workspace_id)
            session.add(health)
        health.status = status
        health.latency_ms = latency_ms
        health.safe_error_code = safe_error_code
        health.checked_at = get_current_utc_datetime()
        await session.commit()
    return {"providerAccountId": str(account_id), "status": status.value, "latencyMs": latency_ms, "safeErrorCode": safe_error_code}


def register_provider_handlers(registry: JobRegistry) -> None:
    definition = OperationDefinition(
        "provider.connection_test", QueueClass.MAINTENANCE,
        ProviderConnectionTestPayload, test_provider_connection, max_attempts=2,
        required_permissions=(Permission.CREDENTIALS_MANAGE,),
    )
    if registry.get(definition.operation) is None:
        registry.register(definition)
