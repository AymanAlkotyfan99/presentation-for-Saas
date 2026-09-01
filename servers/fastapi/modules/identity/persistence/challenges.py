"""Purpose-challenge persistence and shared delivery eligibility."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.sql.user import User
from modules.identity.persistence.identifiers import lock_identifier_claim
from modules.identity.persistence.models import (
    AccountLoginIdentifier,
    AccountPurposeChallenge,
    PendingRegistration,
)
from modules.identity.persistence.pending_registrations import (
    lock_pending_registration,
)
from modules.identity.persistence.repositories import locked


@dataclass(frozen=True)
class DeliveryEligibility:
    eligible: bool
    reason: str
    challenge_id: UUID
    subject_id: UUID | None = None
    subject_kind: str | None = None
    purpose: str | None = None
    key_version: str | None = None
    binding_generation: int | None = None
    token_digest: str | None = field(default=None, repr=False)
    recipient: str | None = field(default=None, repr=False)
    locale: str | None = None


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


async def get_challenge(
    session: AsyncSession, challenge_id: UUID
) -> AccountPurposeChallenge | None:
    return await session.get(AccountPurposeChallenge, challenge_id)


async def lock_challenge(
    session: AsyncSession, challenge_id: UUID
) -> AccountPurposeChallenge | None:
    statement = select(AccountPurposeChallenge).where(
        AccountPurposeChallenge.id == challenge_id
    )
    return await session.scalar(locked(statement, session))


async def compare_and_set_challenge_not_current(
    session: AsyncSession,
    *,
    challenge_id: UUID,
    expected_issue_generation: int,
    revoked_at: datetime,
    reason: str,
) -> bool:
    result = await session.execute(
        update(AccountPurposeChallenge)
        .where(
            AccountPurposeChallenge.id == challenge_id,
            AccountPurposeChallenge.issue_generation == expected_issue_generation,
            AccountPurposeChallenge.is_current.is_(True),
            AccountPurposeChallenge.consumed_at.is_(None),
            AccountPurposeChallenge.revoked_at.is_(None),
        )
        .values(is_current=False, revoked_at=revoked_at, revocation_reason=reason)
    )
    return result.rowcount == 1


async def _lock_user(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.scalar(
        locked(select(User).where(User.id == user_id), session)
    )


async def read_delivery_eligibility(
    session: AsyncSession,
    *,
    challenge_id: UUID,
    now: datetime,
    for_update: bool = False,
) -> DeliveryEligibility:
    """Re-read challenge, subject, binding, claim, and lease authority.

    When ``for_update`` is true, the caller must first use
    ``acquire_identity_write_lock``. An unlocked locator read discovers the
    subject; every authoritative value is then re-read in the canonical order.
    """

    discovered = await get_challenge(session, challenge_id)
    if discovered is None:
        return DeliveryEligibility(False, "CHALLENGE_NOT_FOUND", challenge_id)

    pending: PendingRegistration | None = None
    user: User | None = None
    normalized: str | None = None
    if discovered.pending_registration_id is not None:
        pending = await session.get(
            PendingRegistration, discovered.pending_registration_id
        )
        normalized = pending.email_normalized if pending else None
    elif discovered.user_id is not None:
        user = await session.get(User, discovered.user_id)
        normalized = user.email_normalized if user else None

    claim = None
    if normalized is not None:
        claim = (
            await lock_identifier_claim(session, normalized)
            if for_update
            else await session.get(AccountLoginIdentifier, normalized)
        )
    if for_update:
        if pending is not None:
            pending = await lock_pending_registration(session, pending.id)
        elif user is not None:
            user = await _lock_user(session, user.id)
        challenge = await lock_challenge(session, challenge_id)
    else:
        challenge = discovered

    if challenge is None:
        return DeliveryEligibility(False, "CHALLENGE_NOT_FOUND", challenge_id)
    if not challenge.is_current:
        return DeliveryEligibility(False, "CHALLENGE_NOT_CURRENT", challenge_id)
    if challenge.consumed_at is not None or challenge.revoked_at is not None:
        return DeliveryEligibility(False, "CHALLENGE_TERMINAL", challenge_id)
    if _utc(challenge.expires_at) <= _utc(now):
        return DeliveryEligibility(False, "CHALLENGE_EXPIRED", challenge_id)

    if challenge.subject_kind == "PENDING_REGISTRATION":
        if pending is None or challenge.pending_registration_id != pending.id:
            return DeliveryEligibility(False, "SUBJECT_NOT_FOUND", challenge_id)
        if (
            challenge.purpose != "EMAIL_VERIFICATION"
            or pending.state != "PENDING"
            or _utc(pending.reclaim_after) <= _utc(now)
            or challenge.binding_generation != pending.claim_generation
            or not pending.email_original
            or not pending.email_normalized
            or claim is None
            or claim.pending_registration_id != pending.id
            or claim.user_id is not None
            or claim.kind != "EMAIL"
        ):
            return DeliveryEligibility(False, "SUBJECT_INELIGIBLE", challenge_id)
        return DeliveryEligibility(
            True,
            "ELIGIBLE",
            challenge_id,
            subject_id=pending.id,
            subject_kind=challenge.subject_kind,
            purpose=challenge.purpose,
            key_version=challenge.key_version,
            binding_generation=challenge.binding_generation,
            token_digest=challenge.token_digest,
            recipient=pending.email_original,
            locale=pending.preferred_locale,
        )

    if user is None or challenge.user_id != user.id:
        return DeliveryEligibility(False, "SUBJECT_NOT_FOUND", challenge_id)
    if (
        challenge.subject_kind != "USER"
        or challenge.purpose != "PASSWORD_RESET"
        or not user.is_active
        or user.account_state == "DISABLED"
        or user.email_state != "VERIFIED"
        or challenge.binding_generation != user.auth_version
        or not user.email_original
        or not user.email_normalized
        or claim is None
        or claim.user_id != user.id
        or claim.pending_registration_id is not None
        or claim.kind != "EMAIL"
    ):
        return DeliveryEligibility(False, "SUBJECT_INELIGIBLE", challenge_id)
    return DeliveryEligibility(
        True,
        "ELIGIBLE",
        challenge_id,
        subject_id=user.id,
        subject_kind=challenge.subject_kind,
        purpose=challenge.purpose,
        key_version=challenge.key_version,
        binding_generation=challenge.binding_generation,
        token_digest=challenge.token_digest,
        recipient=user.email_original,
        locale=user.preferred_locale or "en",
    )
