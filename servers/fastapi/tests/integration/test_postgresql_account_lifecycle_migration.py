from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import os
import sys
from uuid import uuid4

from alembic import command
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from modules.identity.persistence.challenges import lock_challenge
from modules.identity.persistence.identifiers import (
    add_identifier_claim,
    lock_identifier_claim,
)
from modules.identity.persistence.models import (
    AccountPurposeChallenge,
    PendingRegistration,
)
from modules.identity.persistence.pending_registrations import (
    compare_and_set_pending_terminal,
    lock_pending_registration,
)
from modules.identity.persistence.repositories import acquire_identity_write_lock

from tests.unit.test_account_lifecycle_migration import (
    PARENT_REVISION,
    alembic_config,
    assert_preserved_after_expand,
    seed_legacy_account_fixture,
)


def _disposable_postgres_url() -> str:
    database_url = os.getenv("MIGRATION_TEST_DATABASE_URL", "")
    if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        pytest.skip(
            "MIGRATION_TEST_DATABASE_URL does not identify disposable PostgreSQL"
        )
    return database_url


def test_expand_migration_preserves_legacy_data_on_disposable_postgresql() -> None:
    database_url = _disposable_postgres_url()
    schema = f"account_lifecycle_{uuid4().hex}"
    admin_engine = create_engine(database_url)
    schema_url = make_url(database_url).update_query_dict(
        {"options": f"-csearch_path={schema}"}
    ).render_as_string(
        hide_password=False
    )
    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))

        config = alembic_config(schema_url)
        command.upgrade(config, PARENT_REVISION)
        seed_legacy_account_fixture(schema_url)
        command.upgrade(config, "head")

        assert_preserved_after_expand(schema_url)
    finally:
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


def test_postgresql_row_locks_and_generation_cas_choose_one_pending_winner() -> None:
    database_url = _disposable_postgres_url()
    schema = f"account_repository_{uuid4().hex}"
    schema_url = make_url(database_url).update_query_dict(
        {"options": f"-csearch_path={schema}"}
    ).render_as_string(hide_password=False)
    admin_engine = create_engine(database_url)

    async def scenario() -> None:
        engine = create_async_engine(schema_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        now = datetime(2026, 9, 1, tzinfo=UTC)
        pending = PendingRegistration(
            state="PENDING",
            email_original="postgres@example.com",
            email_normalized="postgres@example.com",
            preferred_locale="en",
            claim_generation=1,
            created_at=now,
            reclaim_after=now + timedelta(hours=72),
        )
        challenge = AccountPurposeChallenge(
            subject_kind="PENDING_REGISTRATION",
            pending_registration_id=pending.id,
            purpose="EMAIL_VERIFICATION",
            issue_generation=1,
            binding_generation=1,
            key_version="k1",
            token_digest="c" * 64,
            issued_at=now,
            expires_at=now + timedelta(hours=24),
            is_current=True,
        )
        async with sessions() as session:
            session.add(pending)
            await session.flush()
            await add_identifier_claim(
                session,
                normalized_value="postgres@example.com",
                kind="EMAIL",
                pending_registration_id=pending.id,
            )
            session.add(challenge)
            await session.commit()

        async def compete() -> bool:
            async with sessions() as session:
                assert await acquire_identity_write_lock(session) == "postgresql"
                await lock_identifier_claim(session, "postgres@example.com")
                await lock_pending_registration(session, pending.id)
                await lock_challenge(session, challenge.id)
                won = await compare_and_set_pending_terminal(
                    session,
                    pending_registration_id=pending.id,
                    claim_generation=1,
                    target_state="ABANDONED",
                    terminal_at=now + timedelta(hours=72),
                    purge_after=now + timedelta(days=102),
                )
                await session.commit()
                return won

        assert sorted(await asyncio.gather(compete(), compete())) == [False, True]
        await engine.dispose()

    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        command.upgrade(alembic_config(schema_url), "head")
        if sys.platform == "win32":
            loop = asyncio.SelectorEventLoop()
            try:
                loop.run_until_complete(scenario())
            finally:
                loop.close()
        else:
            asyncio.run(scenario())
    finally:
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()
