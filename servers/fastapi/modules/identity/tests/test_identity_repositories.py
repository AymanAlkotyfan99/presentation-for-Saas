from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from models.sql.user import User
from modules.identity.persistence.challenges import read_delivery_eligibility
from modules.identity.persistence.identifiers import (
    add_identifier_claim,
    lock_identifier_claim,
    resolve_user_owned_identifier,
    transfer_pending_claim_to_user,
)
from modules.identity.persistence.models import (
    AccountLoginIdentifier,
    AccountPurposeChallenge,
    PendingRegistration,
)
from modules.identity.persistence.pending_registrations import (
    compare_and_set_pending_terminal,
    lock_pending_registration,
)
from modules.identity.persistence.repositories import (
    LOCK_ORDER,
    acquire_identity_write_lock,
)


TABLES = (
    User.__table__,
    PendingRegistration.__table__,
    AccountLoginIdentifier.__table__,
    AccountPurposeChallenge.__table__,
)


async def _database(tmp_path, name: str):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / name}")

    @event.listens_for(engine.sync_engine, "connect")
    def _foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync: SQLModel.metadata.create_all(sync, tables=TABLES)
        )
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _pending(now: datetime, *, email: str = "victim@example.com"):
    return PendingRegistration(
        state="PENDING",
        email_original=email,
        email_normalized=email.casefold(),
        preferred_locale="en",
        claim_generation=1,
        created_at=now,
        reclaim_after=now + timedelta(hours=72),
    )


def _challenge(pending: PendingRegistration, now: datetime):
    return AccountPurposeChallenge(
        subject_kind="PENDING_REGISTRATION",
        pending_registration_id=pending.id,
        purpose="EMAIL_VERIFICATION",
        issue_generation=1,
        binding_generation=pending.claim_generation,
        key_version="k1",
        token_digest="a" * 64,
        issued_at=now,
        expires_at=now + timedelta(hours=24),
        is_current=True,
    )


def test_pending_registration_has_no_authentication_or_tenant_authority():
    forbidden = {
        "password",
        "hashed_password",
        "auth_version",
        "role",
        "is_superuser",
        "session",
        "workspace_id",
        "membership_id",
    }
    assert forbidden.isdisjoint(PendingRegistration.model_fields)
    assert LOCK_ORDER == (
        "account_login_identifiers",
        "account_pending_registrations_or_user",
        "account_purpose_challenges",
    )


def test_identifier_requires_exact_owner_and_pending_claim_never_resolves_user(
    tmp_path,
):
    async def scenario():
        engine, sessions = await _database(tmp_path, "identifier.db")
        now = datetime(2026, 9, 1, tzinfo=UTC)
        async with sessions() as session:
            user = User(
                username="victim@example.com",
                hashed_password="existing-hash",
            )
            pending = _pending(now)
            session.add_all([user, pending])
            await session.commit()
            user_id = user.id
            pending_id = pending.id

            invalid = AccountLoginIdentifier(
                normalized_value="invalid@example.com",
                kind="EMAIL",
                user_id=user_id,
                pending_registration_id=pending_id,
            )
            session.add(invalid)
            with pytest.raises(IntegrityError):
                await session.commit()
            await session.rollback()

            await add_identifier_claim(
                session,
                normalized_value="victim@example.com",
                kind="EMAIL",
                pending_registration_id=pending_id,
            )
            await session.commit()
            assert (
                await resolve_user_owned_identifier(session, "VICTIM@example.com")
                is None
            )

            assert await transfer_pending_claim_to_user(
                session,
                normalized_value="victim@example.com",
                pending_registration_id=pending_id,
                user_id=user_id,
            )
            await session.commit()
            assert (
                await resolve_user_owned_identifier(session, "victim@example.com")
            ).id == user_id
        await engine.dispose()

    asyncio.run(scenario())


def test_sqlite_serialized_writer_and_generation_cas_have_one_terminal_winner(
    tmp_path,
):
    async def scenario():
        engine, sessions = await _database(tmp_path, "cas.db")
        now = datetime(2026, 9, 1, tzinfo=UTC)
        pending = _pending(now, email="cas@example.com")
        challenge = _challenge(pending, now)
        pending_id = pending.id
        async with sessions() as session:
            session.add(pending)
            await session.flush()
            await add_identifier_claim(
                session,
                normalized_value="cas@example.com",
                kind="EMAIL",
                pending_registration_id=pending_id,
            )
            session.add(challenge)
            await session.commit()

        async with sessions() as first:
            assert await acquire_identity_write_lock(first) == "sqlite"
            assert await lock_identifier_claim(first, "cas@example.com") is not None
            assert await lock_pending_registration(first, pending_id) is not None
            winner = await compare_and_set_pending_terminal(
                first,
                pending_registration_id=pending_id,
                claim_generation=1,
                target_state="ABANDONED",
                terminal_at=now + timedelta(hours=72),
                purge_after=now + timedelta(days=102),
            )
            await first.commit()

        async with sessions() as second:
            assert await acquire_identity_write_lock(second) == "sqlite"
            loser = await compare_and_set_pending_terminal(
                second,
                pending_registration_id=pending_id,
                claim_generation=1,
                target_state="ABANDONED",
                terminal_at=now + timedelta(hours=72),
                purge_after=now + timedelta(days=102),
            )
            await second.rollback()

        assert winner is True
        assert loser is False
        await engine.dispose()

    asyncio.run(scenario())


def test_delivery_eligibility_revalidates_claim_subject_binding_and_lease(tmp_path):
    async def scenario():
        engine, sessions = await _database(tmp_path, "eligibility.db")
        now = datetime(2026, 9, 1, tzinfo=UTC)
        pending = _pending(now, email="eligible@example.com")
        challenge = _challenge(pending, now)
        pending_id = pending.id
        challenge_id = challenge.id
        async with sessions() as session:
            session.add(pending)
            await session.flush()
            await add_identifier_claim(
                session,
                normalized_value="eligible@example.com",
                kind="EMAIL",
                pending_registration_id=pending_id,
            )
            session.add(challenge)
            await session.commit()

        async with sessions() as session:
            await acquire_identity_write_lock(session)
            eligible = await read_delivery_eligibility(
                session,
                challenge_id=challenge_id,
                now=now + timedelta(minutes=1),
                for_update=True,
            )
            assert eligible.eligible is True
            assert eligible.reason == "ELIGIBLE"
            assert eligible.recipient == "eligible@example.com"
            assert "eligible@example.com" not in repr(eligible)
            assert "a" * 64 not in repr(eligible)
            await session.rollback()

        async with sessions() as session:
            stored = await session.get(PendingRegistration, pending_id)
            stored.claim_generation = 2
            await session.commit()
        async with sessions() as session:
            stale = await read_delivery_eligibility(
                session, challenge_id=challenge_id, now=now + timedelta(minutes=2)
            )
            assert stale.eligible is False
            assert stale.reason == "SUBJECT_INELIGIBLE"
        await engine.dispose()

    asyncio.run(scenario())
