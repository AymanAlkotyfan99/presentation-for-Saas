"""Shared lock/CAS policy for identity lifecycle repositories.

Every lifecycle write acquires mutable state in this order:

1. ``AccountLoginIdentifier`` claim;
2. ``PendingRegistration`` or canonical ``User`` subject;
3. ``AccountPurposeChallenge``.

PostgreSQL uses ``SELECT .. FOR UPDATE`` for each authoritative row. SQLite
callers invoke :func:`acquire_identity_write_lock` before any read so the
transaction starts with ``BEGIN IMMEDIATE``; state/generation predicates then
provide the same single-winner observable result. Discovery reads used only to
locate the ordered rows are always revalidated after the locks are acquired.
"""

from __future__ import annotations

from sqlalchemy import Select, text
from sqlalchemy.ext.asyncio import AsyncSession


LOCK_ORDER = (
    "account_login_identifiers",
    "account_pending_registrations_or_user",
    "account_purpose_challenges",
)


async def acquire_identity_write_lock(session: AsyncSession) -> str:
    """Start the supported database's identity writer transaction.

    SQLite must call this before any statement on the session. PostgreSQL can
    join an existing explicit transaction and relies on row-level locks.
    """

    dialect = session.get_bind().dialect.name
    if dialect == "sqlite":
        if session.in_transaction():
            raise RuntimeError(
                "SQLite identity writes must acquire BEGIN IMMEDIATE before any read"
            )
        await session.execute(text("BEGIN IMMEDIATE"))
    elif not session.in_transaction():
        await session.begin()
    return dialect


def locked(statement: Select, session: AsyncSession) -> Select:
    if session.get_bind().dialect.name == "postgresql":
        return statement.with_for_update()
    return statement
