from __future__ import annotations

from datetime import timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from modules.providers.domain.contracts import CapabilityFamily, CircuitState
from modules.providers.persistence.models import ProviderCircuitModel
from utils.datetime_utils import get_current_utc_datetime


def _utc(value):
    return value if value is None or value.tzinfo else value.replace(tzinfo=timezone.utc)


async def allow_call(
    session: AsyncSession,
    *,
    account_id: UUID,
    workspace_id: UUID,
    family: CapabilityFamily,
    model: str,
    probe_seconds: int = 30,
) -> bool:
    now = get_current_utc_datetime()
    row = await session.scalar(
        select(ProviderCircuitModel)
        .where(
            ProviderCircuitModel.provider_account_id == account_id,
            ProviderCircuitModel.family == family,
            ProviderCircuitModel.model == model,
        )
        .with_for_update()
    )
    if row is None:
        row = ProviderCircuitModel(provider_account_id=account_id, workspace_id=workspace_id, family=family, model=model)
        session.add(row); await session.flush()
        return True
    if row.state == CircuitState.CLOSED:
        return True
    if row.state == CircuitState.OPEN:
        if row.opened_until and _utc(row.opened_until) > now:
            return False
        row.state = CircuitState.HALF_OPEN
        row.half_open_probe_until = now + timedelta(seconds=probe_seconds)
        await session.flush()
        return True
    if row.half_open_probe_until and _utc(row.half_open_probe_until) > now:
        return False
    row.half_open_probe_until = now + timedelta(seconds=probe_seconds)
    await session.flush()
    return True


async def record_success(session: AsyncSession, *, account_id: UUID, family: CapabilityFamily, model: str) -> None:
    row = await session.scalar(select(ProviderCircuitModel).where(ProviderCircuitModel.provider_account_id == account_id, ProviderCircuitModel.family == family, ProviderCircuitModel.model == model).with_for_update())
    if row:
        row.state = CircuitState.CLOSED; row.failure_count = 0; row.opened_until = None; row.half_open_probe_until = None; row.window_started_at = get_current_utc_datetime()
        await session.flush()


async def record_failure(
    session: AsyncSession, *, account_id: UUID, family: CapabilityFamily, model: str,
    threshold: int = 3, window_seconds: int = 60, cooldown_seconds: int = 60,
) -> None:
    now = get_current_utc_datetime()
    row = await session.scalar(select(ProviderCircuitModel).where(ProviderCircuitModel.provider_account_id == account_id, ProviderCircuitModel.family == family, ProviderCircuitModel.model == model).with_for_update())
    if row is None:
        return
    if (now - _utc(row.window_started_at)).total_seconds() > window_seconds:
        row.failure_count = 0; row.window_started_at = now
    row.failure_count += 1
    if row.state == CircuitState.HALF_OPEN or row.failure_count >= threshold:
        row.state = CircuitState.OPEN; row.opened_until = now + timedelta(seconds=cooldown_seconds); row.half_open_probe_until = None
    await session.flush()
