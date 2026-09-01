import asyncio
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.v1.auth.router import API_V1_AUTH_ROUTER
from api.v1.auth.rate_limit import LOGIN_RATE_LIMITER, login_rate_limit_key
from api.v1.auth.users import PASSWORD_HELPER
from api.v1.auth.users import UsernameUserDatabase, serialize_user
from models.sql.access_token import AccessToken
from models.sql.user import User
from modules.identity.persistence.identifiers import add_identifier_claim
from modules.identity.persistence.models import (
    AccountLoginIdentifier,
    PendingRegistration,
)
from services.database import get_async_session
from api.v1.auth.config import SESSION_COOKIE_NAME


def _build_client(tmp_path) -> tuple[TestClient, object]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'auth.db'}")
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async def create_user_table():
        async with engine.begin() as connection:
            await connection.run_sync(User.__table__.create)
            await connection.run_sync(AccessToken.__table__.create)
            await connection.run_sync(PendingRegistration.__table__.create)
            await connection.run_sync(AccountLoginIdentifier.__table__.create)

    asyncio.run(create_user_table())

    async def override_session():
        async with session_maker() as session:
            yield session

    app = FastAPI()
    app.include_router(API_V1_AUTH_ROUTER)
    app.dependency_overrides[get_async_session] = override_session
    return TestClient(app), engine


async def _seed_admin(
    engine,
    *,
    username: str = "admin",
    password: str = "unit-test-password",
) -> None:
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            User(
                username=username,
                hashed_password=PASSWORD_HELPER.hash(password),
                is_active=True,
                is_verified=True,
                is_superuser=True,
                admin_slot="primary",
            )
        )
        await session.commit()


def test_public_setup_route_is_not_registered(monkeypatch, tmp_path):
    monkeypatch.delenv("DISABLE_AUTH", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("USER_CONFIG_PATH", str(tmp_path / "userConfig.json"))
    client, engine = _build_client(tmp_path)

    for headers in (
        {},
        {"X-Bootstrap-Secret": "clearly-invalid-test-bootstrap-secret"},
        {"X-Bootstrap-Secret": "clearly-expired-test-bootstrap-secret"},
        {"X-Bootstrap-Secret": "clearly-disabled-test-bootstrap-secret"},
    ):
        response = client.post(
            "/api/v1/auth/setup",
            headers=headers,
            json={"username": "attacker", "password": "unit-test-password"},
        )
        assert response.status_code == 404

    status = client.get("/api/v1/auth/status")
    assert status.status_code == 200
    assert status.json() == {
        "configured": True,
        "authenticated": False,
        "username": None,
        "user_id": None,
        "role": None,
        "preferred_locale": None,
    }
    assert "setup_required" not in status.json()
    client.close()
    asyncio.run(engine.dispose())


def test_login_sets_http_only_jwt_cookie_for_username_only_account(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("USER_CONFIG_PATH", str(tmp_path / "userConfig.json"))
    monkeypatch.delenv("DISABLE_AUTH", raising=False)

    client, engine = _build_client(tmp_path)
    asyncio.run(_seed_admin(engine))
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "ADMIN", "password": "unit-test-password"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is True
    assert payload["authenticated"] is True
    assert payload["username"] == "admin"
    assert "access_token" not in payload
    assert SESSION_COOKIE_NAME in response.cookies
    assert "HttpOnly" in response.headers["set-cookie"]

    client.close()
    asyncio.run(engine.dispose())


def test_authenticated_locale_preference_round_trip(monkeypatch, tmp_path):
    monkeypatch.setenv("USER_CONFIG_PATH", str(tmp_path / "userConfig.json"))
    monkeypatch.delenv("DISABLE_AUTH", raising=False)
    client, engine = _build_client(tmp_path)
    asyncio.run(_seed_admin(engine))

    login = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "unit-test-password"},
    )
    assert login.status_code == 200
    assert login.json()["preferred_locale"] is None

    updated = client.put(
        "/api/v1/auth/preferences/locale",
        json={"preferred_locale": "ar"},
    )
    assert updated.status_code == 200
    assert updated.json() == {"preferred_locale": "ar"}
    assert client.get("/api/v1/auth/preferences/locale").json() == {
        "preferred_locale": "ar"
    }
    assert client.get("/api/v1/auth/status").json()["preferred_locale"] == "ar"

    invalid = client.put(
        "/api/v1/auth/preferences/locale",
        json={"preferred_locale": "fr"},
    )
    assert invalid.status_code == 422

    client.close()
    asyncio.run(engine.dispose())


def test_admin_access_key_passes_internal_auth_check(monkeypatch, tmp_path):
    monkeypatch.setenv("USER_CONFIG_PATH", str(tmp_path / "userConfig.json"))
    monkeypatch.delenv("DISABLE_AUTH", raising=False)
    client, engine = _build_client(tmp_path)
    asyncio.run(_seed_admin(engine))
    client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "unit-test-password"},
    )
    token_response = client.post("/api/v1/auth/token/create")
    token = token_response.json()["token"]
    client.cookies.clear()

    response = client.get(
        "/api/v1/auth/verify",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert token_response.status_code == 200
    assert response.status_code == 200
    assert response.json()["method"] == "api_key"
    assert response.json()["role"] == "admin"

    client.close()
    asyncio.run(engine.dispose())


def test_legacy_six_character_password_can_still_log_in(monkeypatch, tmp_path):
    monkeypatch.setenv("USER_CONFIG_PATH", str(tmp_path / "userConfig.json"))
    monkeypatch.delenv("DISABLE_AUTH", raising=False)
    client, engine = _build_client(tmp_path)

    async def seed_legacy_admin():
        session_maker = async_sessionmaker(engine, expire_on_commit=False)
        async with session_maker() as session:
            session.add(
                User(
                    username="legacy-admin",
                    hashed_password=PASSWORD_HELPER.hash("123456"),
                    is_active=True,
                    is_verified=True,
                    is_superuser=True,
                    admin_slot="primary",
                )
            )
            await session.commit()

    asyncio.run(seed_legacy_admin())
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "legacy-admin", "password": "123456"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "admin"
    client.close()
    asyncio.run(engine.dispose())


def test_failed_logins_are_rate_limited(monkeypatch, tmp_path):
    monkeypatch.setenv("USER_CONFIG_PATH", str(tmp_path / "userConfig.json"))
    monkeypatch.delenv("DISABLE_AUTH", raising=False)
    client, engine = _build_client(tmp_path)
    asyncio.run(
        _seed_admin(
            engine,
            username="rate-admin",
            password="unit-test-password",
        )
    )
    key = login_rate_limit_key("testclient", "rate-admin")
    asyncio.run(LOGIN_RATE_LIMITER.clear(key))

    try:
        for _ in range(5):
            response = client.post(
                "/api/v1/auth/login",
                json={"username": "rate-admin", "password": "wrong-password"},
            )
            assert response.status_code == 401

        blocked = client.post(
            "/api/v1/auth/login",
            json={"username": "rate-admin", "password": "wrong-password"},
        )
        assert blocked.status_code == 429
        assert int(blocked.headers["retry-after"]) > 0
    finally:
        client.close()
        asyncio.run(LOGIN_RATE_LIMITER.clear(key))
        asyncio.run(engine.dispose())


def test_database_rejects_a_second_primary_administrator(monkeypatch, tmp_path):
    monkeypatch.setenv("USER_CONFIG_PATH", str(tmp_path / "userConfig.json"))
    client, engine = _build_client(tmp_path)
    asyncio.run(_seed_admin(engine, username="first-admin"))

    async def insert_second_admin():
        session_maker = async_sessionmaker(engine, expire_on_commit=False)
        async with session_maker() as session:
            session.add(
                User(
                    username="second-admin",
                    hashed_password=PASSWORD_HELPER.hash("another-test-password"),
                    is_active=True,
                    is_verified=True,
                    is_superuser=True,
                    admin_slot="primary",
                )
            )
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                return True
        return False

    assert asyncio.run(insert_second_admin()) is True
    client.close()
    asyncio.run(engine.dispose())


def test_identifier_compatibility_keeps_legacy_username_and_rejects_pending_owner(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("USER_CONFIG_PATH", str(tmp_path / "userConfig.json"))
    client, engine = _build_client(tmp_path)

    async def scenario():
        session_maker = async_sessionmaker(engine, expire_on_commit=False)
        async with session_maker() as session:
            legacy = User(username="legacy-user", hashed_password="legacy-hash")
            shadowed = User(
                username="pending@example.com", hashed_password="shadowed-hash"
            )
            pending = PendingRegistration(
                state="PENDING",
                email_original="pending@example.com",
                email_normalized="pending@example.com",
                preferred_locale="en",
                claim_generation=1,
                reclaim_after=datetime.now(UTC) + timedelta(hours=72),
            )
            session.add_all([legacy, shadowed, pending])
            await session.flush()
            await add_identifier_claim(
                session,
                normalized_value="pending@example.com",
                kind="EMAIL",
                pending_registration_id=pending.id,
            )
            await session.commit()

            database = UsernameUserDatabase(session)
            assert (await database.get_by_email("LEGACY-USER")).id == legacy.id
            assert await database.get_by_email("pending@example.com") is None
            assert serialize_user(legacy)["username"] == "legacy-user"

    asyncio.run(scenario())
    client.close()
    asyncio.run(engine.dispose())
