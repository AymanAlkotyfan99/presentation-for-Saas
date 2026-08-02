import asyncio
import json
import os
import stat

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.v1.auth import bootstrap
from api.v1.auth.users import PASSWORD_HELPER
from models.sql.access_token import AccessToken
from models.sql.user import User


async def _create_auth_database(database_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(User.__table__.create)
        await connection.run_sync(AccessToken.__table__.create)
    return engine, session_maker


async def _skip_ownership_backfill(_session, _admin):
    return None


def test_first_admin_requires_deployment_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("USER_CONFIG_PATH", str(tmp_path / "userConfig.json"))
    monkeypatch.delenv("AUTH_USERNAME", raising=False)
    monkeypatch.delenv("AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("AUTH_OVERRIDE_FROM_ENV", raising=False)
    monkeypatch.delenv("RESET_AUTH", raising=False)
    monkeypatch.delenv("DISABLE_AUTH", raising=False)

    async def runner():
        engine, session_maker = await _create_auth_database(tmp_path / "empty.db")
        try:
            monkeypatch.setattr(bootstrap, "async_session_maker", session_maker)
            monkeypatch.setattr(
                bootstrap,
                "_backfill_legacy_ownership",
                _skip_ownership_backfill,
            )
            with pytest.raises(RuntimeError, match="No administrator is configured"):
                await bootstrap.bootstrap_database_admin()
        finally:
            await engine.dispose()

    asyncio.run(runner())


def test_auth_disabled_allows_startup_without_admin(monkeypatch, tmp_path):
    monkeypatch.setenv("USER_CONFIG_PATH", str(tmp_path / "userConfig.json"))
    monkeypatch.setenv("DISABLE_AUTH", "true")
    monkeypatch.delenv("AUTH_USERNAME", raising=False)
    monkeypatch.delenv("AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("AUTH_OVERRIDE_FROM_ENV", raising=False)
    monkeypatch.delenv("RESET_AUTH", raising=False)

    async def runner():
        engine, session_maker = await _create_auth_database(tmp_path / "disabled.db")
        try:
            monkeypatch.setattr(bootstrap, "async_session_maker", session_maker)
            monkeypatch.setattr(
                bootstrap,
                "_backfill_legacy_ownership",
                _skip_ownership_backfill,
            )
            await bootstrap.bootstrap_database_admin()
            async with session_maker() as session:
                assert list(await session.scalars(select(User))) == []
        finally:
            await engine.dispose()

    asyncio.run(runner())


def test_environment_provisions_exactly_one_admin_and_cannot_be_reused(
    monkeypatch, tmp_path
):
    config_path = tmp_path / "userConfig.json"
    monkeypatch.setenv("USER_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("AUTH_USERNAME", "deployment-admin")
    monkeypatch.setenv("AUTH_PASSWORD", "unit-test-bootstrap-password")
    monkeypatch.delenv("AUTH_OVERRIDE_FROM_ENV", raising=False)
    monkeypatch.delenv("RESET_AUTH", raising=False)
    monkeypatch.delenv("DISABLE_AUTH", raising=False)

    async def runner():
        engine, session_maker = await _create_auth_database(tmp_path / "provision.db")
        try:
            monkeypatch.setattr(bootstrap, "async_session_maker", session_maker)
            monkeypatch.setattr(
                bootstrap,
                "_backfill_legacy_ownership",
                _skip_ownership_backfill,
            )
            await bootstrap.bootstrap_database_admin()
            await bootstrap.bootstrap_database_admin()

            async with session_maker() as session:
                users = list(await session.scalars(select(User)))
            assert len(users) == 1
            assert users[0].username == "deployment-admin"
            assert users[0].is_superuser is True
            assert users[0].admin_slot == "primary"
        finally:
            await engine.dispose()

    asyncio.run(runner())


def test_concurrent_environment_bootstrap_creates_one_admin(monkeypatch, tmp_path):
    monkeypatch.setenv("USER_CONFIG_PATH", str(tmp_path / "userConfig.json"))
    monkeypatch.setenv("AUTH_USERNAME", "concurrent-admin")
    monkeypatch.setenv("AUTH_PASSWORD", "unit-test-bootstrap-password")
    monkeypatch.delenv("AUTH_OVERRIDE_FROM_ENV", raising=False)
    monkeypatch.delenv("RESET_AUTH", raising=False)
    monkeypatch.delenv("DISABLE_AUTH", raising=False)

    async def runner():
        engine, session_maker = await _create_auth_database(tmp_path / "concurrent.db")
        try:
            monkeypatch.setattr(bootstrap, "async_session_maker", session_maker)
            monkeypatch.setattr(
                bootstrap,
                "_backfill_legacy_ownership",
                _skip_ownership_backfill,
            )
            await asyncio.gather(
                bootstrap.bootstrap_database_admin(),
                bootstrap.bootstrap_database_admin(),
            )
            async with session_maker() as session:
                users = list(await session.scalars(select(User)))
            assert len(users) == 1
            assert users[0].username == "concurrent-admin"
            assert users[0].admin_slot == "primary"
        finally:
            await engine.dispose()

    asyncio.run(runner())


def test_first_admin_and_ownership_backfill_commit_atomically(monkeypatch, tmp_path):
    monkeypatch.setenv("USER_CONFIG_PATH", str(tmp_path / "userConfig.json"))
    monkeypatch.setenv("AUTH_USERNAME", "atomic-admin")
    monkeypatch.setenv("AUTH_PASSWORD", "unit-test-bootstrap-password")
    monkeypatch.delenv("AUTH_OVERRIDE_FROM_ENV", raising=False)
    monkeypatch.delenv("RESET_AUTH", raising=False)
    monkeypatch.delenv("DISABLE_AUTH", raising=False)

    async def fail_backfill(_session, _admin):
        raise RuntimeError("synthetic ownership backfill failure")

    async def runner():
        engine, session_maker = await _create_auth_database(tmp_path / "atomic.db")
        try:
            monkeypatch.setattr(bootstrap, "async_session_maker", session_maker)
            monkeypatch.setattr(
                bootstrap,
                "_backfill_legacy_ownership",
                fail_backfill,
            )
            with pytest.raises(RuntimeError, match="synthetic ownership"):
                await bootstrap.bootstrap_database_admin()

            async with session_maker() as session:
                assert list(await session.scalars(select(User))) == []
        finally:
            await engine.dispose()

    asyncio.run(runner())


def test_reset_auth_recovers_admin_without_replacing_account(
    monkeypatch, tmp_path
):
    config_path = tmp_path / "userConfig.json"
    config_path.write_text(
        json.dumps(
            {
                "AUTH_USERNAME": "old-admin",
                "AUTH_PASSWORD_HASH": "old-hash",
                "AUTH_SECRET_KEY": "old-secret",
                "LLM_PROVIDER": "openai",
            }
        )
    )
    monkeypatch.setenv("USER_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("RESET_AUTH", "true")
    monkeypatch.setenv("AUTH_USERNAME", "recovered-admin")
    monkeypatch.setenv("AUTH_PASSWORD", "new-secret-123")
    monkeypatch.delenv("AUTH_OVERRIDE_FROM_ENV", raising=False)

    async def runner():
        engine, session_maker = await _create_auth_database(tmp_path / "auth.db")
        original_id = None
        try:
            async with session_maker() as session:
                admin = User(
                    username="old-admin",
                    hashed_password=PASSWORD_HELPER.hash("old-secret-123"),
                    is_active=True,
                    is_verified=True,
                    is_superuser=True,
                    auth_version=4,
                )
                session.add(admin)
                await session.flush()
                original_id = admin.id
                session.add(AccessToken(token="sk-presenton-old", user_id=admin.id))
                await session.commit()

            async def skip_ownership_backfill(_session, _admin):
                return None

            monkeypatch.setattr(bootstrap, "async_session_maker", session_maker)
            monkeypatch.setattr(
                bootstrap,
                "_backfill_legacy_ownership",
                skip_ownership_backfill,
            )
            await bootstrap.bootstrap_database_admin()

            async with session_maker() as session:
                recovered = await session.scalar(select(User))
                tokens = list(await session.scalars(select(AccessToken)))

            assert recovered is not None
            assert recovered.id == original_id
            assert recovered.username == "recovered-admin"
            assert recovered.admin_slot == "primary"
            assert recovered.auth_version == 5
            verified, _ = PASSWORD_HELPER.verify_and_update(
                "new-secret-123",
                recovered.hashed_password,
            )
            assert verified is True
            assert tokens == []
        finally:
            await engine.dispose()

    asyncio.run(runner())

    config = json.loads(config_path.read_text())
    assert config["AUTH_USERNAME"] == "recovered-admin"
    assert config["AUTH_PASSWORD_HASH"] != "old-hash"
    assert config["AUTH_SECRET_KEY"] != "old-secret"
    assert config["LLM_PROVIDER"] == "openai"
    # POSIX mode bits are enforceable and security-relevant on deployment hosts.
    # Windows maps chmod to a coarse read-only flag and reports 0666 here; ACLs
    # are managed by the deployment filesystem rather than POSIX st_mode.
    if os.name != "nt":
        assert stat.S_IMODE(config_path.stat().st_mode) == 0o600
        assert stat.S_IMODE((tmp_path / "userConfig.json.bak").stat().st_mode) == 0o600


def test_reset_auth_without_password_refuses_to_delete_or_replace_admin(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("USER_CONFIG_PATH", str(tmp_path / "userConfig.json"))
    monkeypatch.setenv("RESET_AUTH", "true")
    monkeypatch.delenv("AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("AUTH_OVERRIDE_FROM_ENV", raising=False)

    async def runner():
        engine, session_maker = await _create_auth_database(
            tmp_path / "missing-password.db"
        )
        try:
            async with session_maker() as session:
                admin = User(
                    username="admin",
                    hashed_password=PASSWORD_HELPER.hash("old-secret-123"),
                    is_active=True,
                    is_verified=True,
                    is_superuser=True,
                    auth_version=1,
                )
                session.add(admin)
                await session.commit()
                original_id = admin.id

            monkeypatch.setattr(bootstrap, "async_session_maker", session_maker)
            with pytest.raises(RuntimeError, match="require AUTH_PASSWORD"):
                await bootstrap.bootstrap_database_admin()

            async with session_maker() as session:
                users = list(await session.scalars(select(User)))
            assert len(users) == 1
            assert users[0].id == original_id
            assert users[0].username == "admin"
        finally:
            await engine.dispose()

    asyncio.run(runner())
