"""Bounded provider-neutral execution with durable routing evidence."""

from __future__ import annotations

import asyncio
import ipaddress
import math
import os
from dataclasses import dataclass
from time import monotonic
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from modules.providers.adapters.registry import PROVIDER_REGISTRY, ProviderExecutionError, ProviderRegistry
from modules.providers.application.circuit import allow_call, record_failure, record_success
from modules.providers.domain.contracts import (
    CapabilityFamily,
    CostEstimate,
    ImageAIAdapterResult,
    ImageAIRequest,
    ImageAIResult,
    NormalizedErrorCode,
    ProviderHealthStatus,
    ProviderRequest,
    ProviderResult,
    SearchRequest,
    SearchResult,
    UsageUnits,
)
from modules.providers.domain.routing import persist_snapshot, plan_route
from modules.providers.persistence.models import ProviderHealthModel, ProviderUsageModel
from modules.providers.security.secrets import EnvironmentMasterKeyProvider, MasterKeyProvider, SecretDecryptionError, resolve_provider_secret
from api.v1.auth.context import get_current_owner_id, get_current_service_account_id
from modules.assets.application.service import ingest_bytes
from utils.architecture_flags import asset_library_enabled, durable_jobs_enabled, object_storage_writes_enabled
from utils.datetime_utils import get_current_utc_datetime


@dataclass(frozen=True)
class ExecutionFailure(RuntimeError):
    code: NormalizedErrorCode
    safe_message: str
    retryable: bool

    def __str__(self) -> str:
        return self.safe_message


def _family(request: ProviderRequest) -> CapabilityFamily:
    from modules.providers.domain.contracts import ImageAIRequest, SearchRequest
    if isinstance(request, ImageAIRequest):
        return CapabilityFamily.IMAGE
    if isinstance(request, SearchRequest):
        return CapabilityFamily.SEARCH
    return CapabilityFamily.TEXT


def _normalize_error(exc: BaseException) -> ExecutionFailure:
    if isinstance(exc, TimeoutError):
        return ExecutionFailure(NormalizedErrorCode.TIMEOUT, "Provider request timed out", True)
    if isinstance(exc, SecretDecryptionError):
        return ExecutionFailure(NormalizedErrorCode.AUTHORIZATION, "Provider credentials are unavailable", False)
    if isinstance(exc, ProviderExecutionError):
        code = {
            "CREDENTIALS_MISSING": NormalizedErrorCode.AUTHORIZATION,
            "RATE_LIMIT": NormalizedErrorCode.RATE_LIMIT,
            "CAPABILITY_MISMATCH": NormalizedErrorCode.CAPABILITY_MISMATCH,
            "INVALID_RESPONSE": NormalizedErrorCode.INVALID_RESPONSE,
            "TIMEOUT": NormalizedErrorCode.TIMEOUT,
            "SERVER_ERROR": NormalizedErrorCode.PROVIDER_UNAVAILABLE,
        }.get(exc.code, NormalizedErrorCode.PROVIDER_UNAVAILABLE)
        return ExecutionFailure(code, exc.safe_message, exc.retryable)
    return ExecutionFailure(NormalizedErrorCode.PROVIDER_UNAVAILABLE, "Provider request failed", True)


def _validate_result(request: ProviderRequest, result: object) -> ProviderResult:
    from modules.providers.domain.contracts import (
        ImageAIRequest,
        ImageAIResult,
        SearchRequest,
        SearchResult,
        TextAIResult,
    )

    expected = (
        ImageAIResult
        if isinstance(request, ImageAIRequest)
        else SearchResult
        if isinstance(request, SearchRequest)
        else TextAIResult
    )
    if not isinstance(result, expected):
        raise ProviderExecutionError(
            "INVALID_RESPONSE",
            "Provider returned an invalid normalized response",
            retryable=True,
        )
    try:
        maximum = int(os.getenv("PROVIDER_MAX_RESPONSE_BYTES", str(2 * 1024 * 1024)))
    except ValueError:
        maximum = 2 * 1024 * 1024
    maximum = max(1024, min(maximum, 16 * 1024 * 1024))
    if len(result.model_dump_json().encode("utf-8")) > maximum:
        raise ProviderExecutionError(
            "INVALID_RESPONSE",
            "Provider normalized response exceeds the configured size limit",
            retryable=True,
        )
    return result


def _bounded_integer_env(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(value, maximum))


def _validate_request_size(request: ProviderRequest) -> None:
    maximum = _bounded_integer_env(
        "PROVIDER_MAX_REQUEST_BYTES", 4 * 1024 * 1024,
        minimum=1024, maximum=16 * 1024 * 1024,
    )
    if len(request.model_dump_json().encode("utf-8")) > maximum:
        raise ExecutionFailure(
            NormalizedErrorCode.INVALID_RESPONSE,
            "Provider request exceeds the configured size limit",
            False,
        )


def _safe_search_url(value: str) -> str:
    try:
        parsed = urlsplit(value.strip())
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError
        try:
            address = ipaddress.ip_address(parsed.hostname)
        except ValueError:
            address = None
        if address is not None and (
            address.is_private or address.is_loopback or address.is_link_local
            or address.is_multicast or address.is_reserved or address.is_unspecified
        ):
            raise ValueError
        return urlunsplit((parsed.scheme.lower(), parsed.netloc, parsed.path, parsed.query, ""))
    except (TypeError, ValueError) as exc:
        raise ProviderExecutionError(
            "INVALID_RESPONSE", "Provider returned an unsafe search URL", retryable=True,
        ) from exc


def _estimate_cost(*, usage: UsageUnits, current: CostEstimate, safe_config: dict) -> CostEstimate:
    if current.amount is not None:
        return current
    terms = (
        (usage.input_tokens, safe_config.get("price_input_per_million"), 1_000_000),
        (usage.output_tokens, safe_config.get("price_output_per_million"), 1_000_000),
        (usage.images, safe_config.get("price_per_image"), 1),
        (usage.search_calls, safe_config.get("price_per_search"), 1),
    )
    amount = 0.0
    priced = False
    for units, raw_price, divisor in terms:
        if units is None or raw_price is None:
            continue
        try:
            price = float(raw_price)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(price) or price < 0:
            continue
        amount += units * price / divisor
        priced = True
    return CostEstimate(
        amount=round(amount, 12) if priced else None,
        currency=(str(safe_config.get("currency"))[:8] if priced and safe_config.get("currency") else None),
        pricing_snapshot_id=(str(safe_config.get("pricing_version"))[:128] if priced and safe_config.get("pricing_version") else None),
    )


async def _normalize_adapter_result(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    request: ProviderRequest,
    raw_result: object,
) -> ProviderResult:
    if isinstance(request, ImageAIRequest) and isinstance(raw_result, ImageAIAdapterResult):
        if not (object_storage_writes_enabled() and asset_library_enabled() and durable_jobs_enabled()):
            raise ProviderExecutionError(
                "CAPABILITY_MISMATCH",
                "Managed asset storage and durable scanning are required for provider images",
                retryable=False,
            )
        maximum = _bounded_integer_env(
            "PROVIDER_MAX_IMAGE_BYTES", 25 * 1024 * 1024,
            minimum=1024, maximum=100 * 1024 * 1024,
        )
        asset_ids: list[UUID] = []
        for index, output in enumerate(raw_result.outputs):
            # Official adapters must resolve remote URLs before this trust boundary.
            if output.data is None or len(output.data) > maximum:
                raise ProviderExecutionError(
                    "INVALID_RESPONSE", "Provider image bytes are missing or exceed the configured limit", retryable=False,
                )
            asset = await ingest_bytes(
                session,
                workspace_id=workspace_id,
                actor_id=get_current_owner_id(),
                actor_service_account_id=get_current_service_account_id(),
                data=output.data,
                filename=output.filename or f"provider-image-{index + 1}.png",
                declared_mime=output.mime_type,
            )
            asset_ids.append(asset.id)
        return ImageAIResult(
            asset_ids=asset_ids,
            usage=raw_result.usage,
            model=raw_result.model,
            cost=raw_result.cost,
        )
    if isinstance(request, SearchRequest) and isinstance(raw_result, SearchResult):
        items = [
            item.model_copy(update={"url": _safe_search_url(item.url)})
            for item in raw_result.items[:request.result_count]
        ]
        return raw_result.model_copy(update={"items": items})
    return _validate_result(request, raw_result)


def _usage_event(
    *,
    workspace_id: UUID,
    candidate,
    snapshot_id: UUID,
    job_id: UUID | None,
    operation: str,
    latency_ms: int,
    status: str,
    safe_error_code: str | None = None,
    result: ProviderResult | None = None,
) -> ProviderUsageModel:
    usage = result.usage if result is not None else UsageUnits()
    cost = result.cost if result is not None else CostEstimate()
    return ProviderUsageModel(
        workspace_id=workspace_id,
        provider_account_id=candidate.account.id,
        provider_snapshot_id=snapshot_id,
        job_id=job_id,
        adapter_id=candidate.account.adapter_id,
        family=candidate.capability.family,
        model=(getattr(result, "model", None) or candidate.capability.model),
        operation=operation[:128],
        status=status,
        safe_error_code=safe_error_code,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        image_count=usage.images,
        search_count=usage.search_calls,
        latency_ms=min(max(0, latency_ms), 2_147_483_647),
        estimated_cost=cost.amount,
        currency=cost.currency,
        pricing_snapshot_id=cost.pricing_snapshot_id,
    )


async def _update_health(
    session: AsyncSession,
    *,
    account_id: UUID,
    workspace_id: UUID,
    status: ProviderHealthStatus,
    latency_ms: int,
    safe_error_code: str | None,
) -> None:
    row = await session.scalar(select(ProviderHealthModel).where(
        ProviderHealthModel.provider_account_id == account_id,
    ).with_for_update())
    if row is None:
        row = ProviderHealthModel(provider_account_id=account_id, workspace_id=workspace_id)
        session.add(row)
    row.status = status
    row.latency_ms = min(max(0, latency_ms), 2_147_483_647)
    row.safe_error_code = safe_error_code
    row.checked_at = get_current_utc_datetime()


class ProviderExecutor:
    def __init__(self, *, registry: ProviderRegistry = PROVIDER_REGISTRY, keys: MasterKeyProvider | None = None) -> None:
        self.registry = registry
        self.keys = keys or EnvironmentMasterKeyProvider()

    async def execute(
        self,
        session: AsyncSession,
        *,
        workspace_id: UUID,
        request: ProviderRequest,
        pinned_account_id: UUID | None = None,
        region: str | None = None,
        plan: str | None = None,
        job_id: UUID | None = None,
        operation: str = "provider.execute",
    ) -> ProviderResult:
        _validate_request_size(request)
        family = _family(request)
        plan_result = await plan_route(
            session, workspace_id=workspace_id, family=family,
            model=getattr(request, "model", None), pinned_account_id=pinned_account_id,
            region=region, plan=plan, registry=self.registry,
        )
        if not plan_result.candidates:
            raise ExecutionFailure(NormalizedErrorCode.POLICY_BLOCKED, "No provider is available under current policy", False)
        previous: ExecutionFailure | None = None
        for candidate in plan_result.candidates:
            if not await allow_call(
                session, account_id=candidate.account.id, workspace_id=workspace_id,
                family=family, model=candidate.capability.model,
            ):
                previous = ExecutionFailure(NormalizedErrorCode.CIRCUIT_OPEN, "Provider circuit is open", True)
                continue
            snapshot = await persist_snapshot(
                session, workspace_id=workspace_id, candidate=candidate,
                policy=plan_result.policy, job_id=job_id,
                fallback_reason=previous.code.value if previous else None,
            )
            await session.commit()
            secret: str | None = None
            started = monotonic()
            try:
                secret = await resolve_provider_secret(session, account_id=candidate.account.id, keys=self.keys)
                candidate_request = request
                if hasattr(request, "model") and getattr(request, "model", None) is None:
                    candidate_request = request.model_copy(update={"model": candidate.capability.model})
                candidate_config = dict(candidate.account.safe_config)
                candidate_config.setdefault("model", candidate.account.default_model or candidate.capability.model)
                async with asyncio.timeout(float(getattr(request, "timeout_seconds", 60))):
                    raw_result = await candidate.adapter.execute(candidate_request, secret=secret, safe_config=candidate_config)
                    result = await _normalize_adapter_result(
                        session, workspace_id=workspace_id, request=candidate_request, raw_result=raw_result,
                    )
                cost = _estimate_cost(usage=result.usage, current=result.cost, safe_config=candidate_config)
                result = _validate_result(candidate_request, result.model_copy(update={"provider_snapshot_id": snapshot.id, "cost": cost}))
                await record_success(session, account_id=candidate.account.id, family=family, model=candidate.capability.model)
                latency_ms = int((monotonic() - started) * 1000)
                await _update_health(
                    session, account_id=candidate.account.id, workspace_id=workspace_id,
                    status=ProviderHealthStatus.HEALTHY,
                    latency_ms=latency_ms, safe_error_code=None,
                )
                session.add(_usage_event(
                    workspace_id=workspace_id, candidate=candidate, snapshot_id=snapshot.id,
                    job_id=job_id, operation=operation, latency_ms=latency_ms,
                    status="SUCCEEDED", result=result,
                ))
                await session.commit()
                return result
            except BaseException as exc:
                if isinstance(exc, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)):
                    raise
                previous = _normalize_error(exc)
                await record_failure(session, account_id=candidate.account.id, family=family, model=candidate.capability.model)
                latency_ms = int((monotonic() - started) * 1000)
                await _update_health(
                    session, account_id=candidate.account.id, workspace_id=workspace_id,
                    status=ProviderHealthStatus.DEGRADED if previous.retryable else ProviderHealthStatus.UNHEALTHY,
                    latency_ms=latency_ms, safe_error_code=previous.code.value,
                )
                session.add(_usage_event(
                    workspace_id=workspace_id, candidate=candidate, snapshot_id=snapshot.id,
                    job_id=job_id, operation=operation, latency_ms=latency_ms,
                    status="FAILED", safe_error_code=previous.code.value,
                ))
                await session.commit()
                if not previous.retryable or pinned_account_id is not None:
                    raise previous from exc
            finally:
                # Avoid retaining credential references beyond the adapter call.
                secret = None
                _ = monotonic() - started  # observability hook; prompt/content is never recorded.
        raise previous or ExecutionFailure(NormalizedErrorCode.PROVIDER_UNAVAILABLE, "Provider request failed", True)
