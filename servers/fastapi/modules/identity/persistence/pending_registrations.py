"""Minimal pending-registration persistence operations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from modules.identity.persistence.models import PendingRegistration
from modules.identity.persistence.repositories import locked


async def get_pending_registration(
    session: AsyncSession, pending_registration_id: UUID
) -> PendingRegistration | None:
    return await session.get(PendingRegistration, pending_registration_id)


async def lock_pending_registration(
    session: AsyncSession, pending_registration_id: UUID
) -> PendingRegistration | None:
    statement = select(PendingRegistration).where(
        PendingRegistration.id == pending_registration_id
    )
    return await session.scalar(locked(statement, session))


async def compare_and_set_pending_terminal(
    session: AsyncSession,
    *,
    pending_registration_id: UUID,
    claim_generation: int,
    target_state: str,
    terminal_at: datetime,
    purge_after: datetime,
    activated_user_id: UUID | None = None,
) -> bool:
    if target_state not in {"ACTIVATED", "ABANDONED"}:
        raise ValueError("Pending registration target must be terminal")
    if target_state == "ACTIVATED" and activated_user_id is None:
        raise ValueError("Activated pending registration requires a canonical user")
    if target_state == "ABANDONED" and activated_user_id is not None:
        raise ValueError("Abandoned pending registration cannot reference a user")
    result = await session.execute(
        update(PendingRegistration)
        .where(
            PendingRegistration.id == pending_registration_id,
            PendingRegistration.state == "PENDING",
            PendingRegistration.claim_generation == claim_generation,
        )
        .values(
            state=target_state,
            email_original=None,
            email_normalized=None,
            terminal_at=terminal_at,
            purge_after=purge_after,
            activated_user_id=activated_user_id,
        )
    )
    return result.rowcount == 1
