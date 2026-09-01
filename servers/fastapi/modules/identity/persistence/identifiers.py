"""Authoritative global login-identifier claims."""

from __future__ import annotations

import unicodedata
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.sql.user import User
from modules.identity.persistence.models import AccountLoginIdentifier
from modules.identity.persistence.repositories import locked


class IdentifierClaimConflict(RuntimeError):
    """A requested global identifier is already claimed."""


def normalize_legacy_username(value: str) -> str:
    return unicodedata.normalize("NFC", value.strip()).casefold()


async def get_identifier_claim(
    session: AsyncSession, normalized_value: str
) -> AccountLoginIdentifier | None:
    return await session.get(AccountLoginIdentifier, normalized_value)


async def lock_identifier_claim(
    session: AsyncSession, normalized_value: str
) -> AccountLoginIdentifier | None:
    statement = select(AccountLoginIdentifier).where(
        AccountLoginIdentifier.normalized_value == normalized_value
    )
    return await session.scalar(locked(statement, session))


def _require_exact_owner(
    *, user_id: UUID | None, pending_registration_id: UUID | None
) -> None:
    if (user_id is None) == (pending_registration_id is None):
        raise ValueError("An identifier claim requires exactly one owner kind")


async def add_identifier_claim(
    session: AsyncSession,
    *,
    normalized_value: str,
    kind: str,
    user_id: UUID | None = None,
    pending_registration_id: UUID | None = None,
) -> AccountLoginIdentifier:
    _require_exact_owner(
        user_id=user_id, pending_registration_id=pending_registration_id
    )
    claim = AccountLoginIdentifier(
        normalized_value=normalized_value,
        kind=kind,
        user_id=user_id,
        pending_registration_id=pending_registration_id,
    )
    session.add(claim)
    await session.flush()
    return claim


async def transfer_pending_claim_to_user(
    session: AsyncSession,
    *,
    normalized_value: str,
    pending_registration_id: UUID,
    user_id: UUID,
) -> bool:
    result = await session.execute(
        update(AccountLoginIdentifier)
        .where(
            AccountLoginIdentifier.normalized_value == normalized_value,
            AccountLoginIdentifier.pending_registration_id
            == pending_registration_id,
            AccountLoginIdentifier.user_id.is_(None),
            AccountLoginIdentifier.kind == "EMAIL",
        )
        .values(user_id=user_id, pending_registration_id=None)
    )
    return result.rowcount == 1


async def release_pending_claim(
    session: AsyncSession,
    *,
    normalized_value: str,
    pending_registration_id: UUID,
) -> bool:
    result = await session.execute(
        delete(AccountLoginIdentifier).where(
            AccountLoginIdentifier.normalized_value == normalized_value,
            AccountLoginIdentifier.pending_registration_id
            == pending_registration_id,
            AccountLoginIdentifier.user_id.is_(None),
        )
    )
    return result.rowcount == 1


async def resolve_user_owned_identifier(
    session: AsyncSession, identifier: str
) -> User | None:
    """Resolve only a user-owned claim, with a flags-off legacy fallback.

    A present pending claim deliberately suppresses the fallback, so a pending
    reservation can never become a login principal. Email login policy is not
    enabled here; the fallback remains username-only.
    """

    normalized = normalize_legacy_username(identifier)
    claim = await get_identifier_claim(session, normalized)
    if claim is not None:
        if claim.user_id is None:
            return None
        return await session.get(User, claim.user_id)
    return await session.scalar(
        select(User).where(User.username.is_not(None)).where(
            User.username.collate("NOCASE") == identifier.strip()
            if session.get_bind().dialect.name == "sqlite"
            else User.username.ilike(identifier.strip())
        )
    )
