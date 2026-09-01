from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
import pytest


PARENT_REVISION = "d4f6a8c0e2b3"
EXPAND_REVISION = "e5a7c9d1f3b4"

LEGACY_USER_ID = UUID("00000000-0000-4000-8000-000000000101")
PRIMARY_ADMIN_ID = UUID("00000000-0000-4000-8000-000000000102")
LEGACY_WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000201")
ADMIN_WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000202")
INVITATION_ID = UUID("00000000-0000-4000-8000-000000000301")
JOB_ID = UUID("00000000-0000-4000-8000-000000000401")


def _database_uuid(database_url: str, value: UUID) -> UUID | str:
    return value.hex if database_url.startswith("sqlite") else value


def alembic_config(database_url: str) -> Config:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    # ConfigParser treats percent-encoded URL bytes as interpolation syntax.
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def test_alembic_upgrade_preserves_existing_application_loggers(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'logging-isolation.db').as_posix()}"
    application_logger = logging.getLogger("bayanly.test.migration-logging-isolation")
    original_disabled = application_logger.disabled
    application_logger.disabled = False

    try:
        command.upgrade(alembic_config(database_url), "head")

        assert application_logger.disabled is False
    finally:
        application_logger.disabled = original_disabled


def seed_legacy_account_fixture(database_url: str) -> None:
    legacy_id = _database_uuid(database_url, LEGACY_USER_ID)
    admin_id = _database_uuid(database_url, PRIMARY_ADMIN_ID)
    legacy_workspace = _database_uuid(database_url, LEGACY_WORKSPACE_ID)
    admin_workspace = _database_uuid(database_url, ADMIN_WORKSPACE_ID)
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO "user"
                        (id, username, admin_slot, hashed_password, is_active,
                         is_superuser, is_verified, created_at, auth_version,
                         preferred_locale)
                    VALUES
                        (:legacy_id, 'LegacyUser', NULL, 'legacy-user-hash', true,
                         false, true, CURRENT_TIMESTAMP, 7, 'ar'),
                        (:admin_id, 'PrimaryAdmin', 'primary', 'primary-admin-hash',
                         true, true, false, CURRENT_TIMESTAMP, 11, 'en')
                    """
                ),
                {"legacy_id": legacy_id, "admin_id": admin_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO access_tokens (token, user_id, created_at)
                    VALUES ('legacy-session-fixture', :admin_id, CURRENT_TIMESTAMP)
                    """
                ),
                {"admin_id": admin_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO workspaces
                        (id, name, is_personal, personal_owner_id, created_by,
                         created_at, updated_at)
                    VALUES
                        (:legacy_workspace, 'Legacy workspace', true, :legacy_id,
                         :legacy_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                        (:admin_workspace, 'Admin workspace', true, :admin_id,
                         :admin_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """
                ),
                {
                    "legacy_workspace": legacy_workspace,
                    "admin_workspace": admin_workspace,
                    "legacy_id": legacy_id,
                    "admin_id": admin_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO memberships
                        (id, workspace_id, user_id, role, status,
                         permission_overrides, created_at, updated_at)
                    VALUES
                        (:legacy_id, :legacy_workspace, :legacy_id, 'OWNER', 'ACTIVE',
                         '[]', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                        (:admin_id, :admin_workspace, :admin_id, 'OWNER', 'ACTIVE',
                         '[]', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """
                ),
                {
                    "legacy_id": legacy_id,
                    "admin_id": admin_id,
                    "legacy_workspace": legacy_workspace,
                    "admin_workspace": admin_workspace,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO invitations
                        (id, workspace_id, invited_identity, role, token_digest,
                         created_by, created_at, expires_at, send_count)
                    VALUES
                        (:invitation_id, :workspace_id, 'LegacyUser', 'VIEWER',
                         :token_digest, :admin_id, CURRENT_TIMESTAMP,
                         CURRENT_TIMESTAMP, 2)
                    """
                ),
                {
                    "invitation_id": _database_uuid(database_url, INVITATION_ID),
                    "workspace_id": admin_workspace,
                    "admin_id": admin_id,
                    "token_digest": "a" * 64,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO jobs
                        (id, workspace_id, owner_id, actor_id, operation, queue_class,
                         status, progress, payload, payload_schema_version,
                         result_schema_version, request_hash, idempotency_scope,
                         idempotency_key, attempt_count, max_attempts, available_at,
                         created_at, updated_at)
                    VALUES
                        (:job_id, :workspace_id, :admin_id, :admin_id, 'test.legacy',
                         'maintenance', 'PENDING', 0, '{}', 1, 1, :request_hash,
                         'legacy:migration', 'fixture', 0, 3, CURRENT_TIMESTAMP,
                         CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """
                ),
                {
                    "job_id": _database_uuid(database_url, JOB_ID),
                    "workspace_id": admin_workspace,
                    "admin_id": admin_id,
                    "request_hash": "b" * 64,
                },
            )
    finally:
        engine.dispose()


def assert_preserved_after_expand(database_url: str) -> None:
    legacy_id = _database_uuid(database_url, LEGACY_USER_ID)
    admin_id = _database_uuid(database_url, PRIMARY_ADMIN_ID)
    legacy_workspace = _database_uuid(database_url, LEGACY_WORKSPACE_ID)
    admin_workspace = _database_uuid(database_url, ADMIN_WORKSPACE_ID)
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert {
            "account_pending_registrations",
            "account_login_identifiers",
            "account_purpose_challenges",
            "account_lifecycle_audit_events",
            "account_notification_deliveries",
        }.issubset(inspector.get_table_names())

        with engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            users = connection.execute(
                text(
                    """
                    SELECT id, username, admin_slot, hashed_password, is_active,
                           is_superuser, is_verified, created_at, auth_version,
                           preferred_locale,
                           account_origin, account_state, email_state,
                           email_original, email_normalized, email_verified_at
                    FROM "user" ORDER BY username
                    """
                )
            ).mappings().all()
            claims = connection.execute(
                text(
                    """
                    SELECT normalized_value, kind, user_id, pending_registration_id
                    FROM account_login_identifiers ORDER BY normalized_value
                    """
                )
            ).mappings().all()
            invitation = connection.execute(
                text(
                    """
                    SELECT id, workspace_id, invited_identity,
                           normalized_identity, identity_kind, role, token_digest,
                           created_by, created_at, expires_at, send_count
                    FROM invitations WHERE id = :id
                    """
                ),
                {"id": _database_uuid(database_url, INVITATION_ID)},
            ).mappings().one()
            memberships = connection.execute(
                text(
                    """
                    SELECT id, workspace_id, user_id, role, status,
                           permission_overrides, created_at, updated_at
                    FROM memberships
                    WHERE (workspace_id = :legacy_workspace AND user_id = :legacy_id)
                       OR (workspace_id = :admin_workspace AND user_id = :admin_id)
                    ORDER BY user_id
                    """
                ),
                {
                    "legacy_workspace": legacy_workspace,
                    "admin_workspace": admin_workspace,
                    "legacy_id": legacy_id,
                    "admin_id": admin_id,
                },
            ).mappings().all()
            workspaces = connection.execute(
                text(
                    """
                    SELECT id, name, is_personal, personal_owner_id, created_by,
                           created_at, updated_at
                    FROM workspaces
                    WHERE id IN (:legacy_workspace, :admin_workspace)
                    ORDER BY name
                    """
                ),
                {
                    "legacy_workspace": legacy_workspace,
                    "admin_workspace": admin_workspace,
                },
            ).mappings().all()
            job = connection.execute(
                text(
                    """
                    SELECT id, workspace_id, owner_id, actor_id,
                           actor_service_account_id, operation, queue_class, status,
                           progress, request_hash, authority_kind,
                           idempotency_scope, idempotency_key, attempt_count,
                           max_attempts, created_at, updated_at
                    FROM jobs WHERE id = :id
                    """
                ),
                {"id": _database_uuid(database_url, JOB_ID)},
            ).mappings().one()
            token = connection.execute(
                text(
                    "SELECT token, user_id, created_at FROM access_tokens "
                    "WHERE token = :token"
                ),
                {"token": "legacy-session-fixture"},
            ).mappings().one()

        assert revision == EXPAND_REVISION
        assert len(users) == 2
        by_name = {row["username"]: row for row in users}
        legacy = by_name["LegacyUser"]
        admin = by_name["PrimaryAdmin"]
        assert legacy["id"] == legacy_id
        assert admin["id"] == admin_id
        assert (
            legacy["hashed_password"],
            legacy["is_active"],
            legacy["is_superuser"],
            legacy["is_verified"],
            legacy["auth_version"],
            legacy["preferred_locale"],
        ) == ("legacy-user-hash", True, False, True, 7, "ar")
        assert legacy["created_at"] is not None
        assert (
            admin["admin_slot"],
            admin["hashed_password"],
            admin["is_active"],
            admin["is_superuser"],
            admin["is_verified"],
            admin["auth_version"],
        ) == ("primary", "primary-admin-hash", True, True, False, 11)
        assert admin["created_at"] is not None
        assert legacy["account_origin"] == "ADMIN_PROVISIONED"
        assert admin["account_origin"] == "GRANDFATHERED"
        assert {row["account_state"] for row in users} == {"ACTIVE"}
        assert {row["email_state"] for row in users} == {"UNSET"}
        assert all(
            row["email_original"] is None
            and row["email_normalized"] is None
            and row["email_verified_at"] is None
            for row in users
        ), "historical is_verified must never become verified-email proof"
        assert [row["normalized_value"] for row in claims] == [
            "legacyuser",
            "primaryadmin",
        ]
        assert all(
            row["kind"] == "USERNAME"
            and row["user_id"] is not None
            and row["pending_registration_id"] is None
            for row in claims
        )
        assert invitation["id"] == _database_uuid(database_url, INVITATION_ID)
        assert invitation["workspace_id"] == admin_workspace
        assert invitation["invited_identity"] == "LegacyUser"
        assert invitation["normalized_identity"] == "legacyuser"
        assert invitation["identity_kind"] == "USERNAME"
        assert invitation["role"] == "VIEWER"
        assert invitation["token_digest"] == "a" * 64
        assert invitation["created_by"] == admin_id
        assert invitation["created_at"] is not None
        assert invitation["expires_at"] is not None
        assert invitation["send_count"] == 2
        assert len(memberships) == 2
        assert {row["id"] for row in memberships} == {legacy_id, admin_id}
        assert all(
            row["role"] == "OWNER" and row["status"] == "ACTIVE"
            for row in memberships
        )
        assert all(
            row["permission_overrides"] in ("[]", [])
            and row["created_at"] is not None
            and row["updated_at"] is not None
            for row in memberships
        )
        assert len(workspaces) == 2
        by_workspace_name = {row["name"]: row for row in workspaces}
        assert by_workspace_name["Legacy workspace"]["id"] == legacy_workspace
        assert by_workspace_name["Legacy workspace"]["personal_owner_id"] == legacy_id
        assert by_workspace_name["Legacy workspace"]["created_by"] == legacy_id
        assert by_workspace_name["Admin workspace"]["id"] == admin_workspace
        assert by_workspace_name["Admin workspace"]["personal_owner_id"] == admin_id
        assert by_workspace_name["Admin workspace"]["created_by"] == admin_id
        assert all(
            row["is_personal"]
            and row["created_at"] is not None
            and row["updated_at"] is not None
            for row in workspaces
        )
        assert job["id"] == _database_uuid(database_url, JOB_ID)
        assert job["workspace_id"] is not None
        assert job["owner_id"] is not None and job["actor_id"] is not None
        assert job["actor_service_account_id"] is None
        assert job["operation"] == "test.legacy"
        assert job["queue_class"] == "maintenance"
        assert job["status"] == "PENDING"
        assert job["progress"] == 0
        assert job["request_hash"] == "b" * 64
        assert job["authority_kind"] == "WORKSPACE"
        assert (job["idempotency_scope"], job["idempotency_key"]) == (
            "legacy:migration",
            "fixture",
        )
        assert (job["attempt_count"], job["max_attempts"]) == (0, 3)
        assert job["created_at"] is not None and job["updated_at"] is not None
        assert token["token"] == "legacy-session-fixture"
        assert token["user_id"] == admin_id
        assert token["created_at"] is not None
    finally:
        engine.dispose()


def test_expand_migration_preserves_legacy_auth_tenant_and_job_data_on_sqlite(
    tmp_path,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'account-lifecycle.db').as_posix()}"
    config = alembic_config(database_url)
    command.upgrade(config, PARENT_REVISION)
    seed_legacy_account_fixture(database_url)

    command.upgrade(config, "head")

    assert_preserved_after_expand(database_url)

    command.downgrade(config, PARENT_REVISION)
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one() == PARENT_REVISION
            preserved = connection.execute(
                text(
                    """
                    SELECT username, hashed_password, is_verified, auth_version
                    FROM "user" ORDER BY username
                    """
                )
            ).all()
        assert preserved == [
            ("LegacyUser", "legacy-user-hash", True, 7),
            ("PrimaryAdmin", "primary-admin-hash", False, 11),
        ]
        assert "account_pending_registrations" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_expand_downgrade_refuses_lifecycle_data_loss(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'downgrade-refusal.db').as_posix()}"
    config = alembic_config(database_url)
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    pending_id = "00000000000040008000000000000501"
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO account_pending_registrations
                        (id, state, email_original, email_normalized,
                         preferred_locale, claim_generation, created_at, reclaim_after)
                    VALUES
                        (:id, 'PENDING', 'private@example.com',
                         'private@example.com', 'en', 1, CURRENT_TIMESTAMP,
                         '2026-09-04 00:00:00')
                    """
                ),
                {"id": pending_id},
            )

        with pytest.raises(RuntimeError, match="downgrade refused"):
            command.downgrade(config, PARENT_REVISION)

        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one() == EXPAND_REVISION
            assert connection.execute(
                text(
                    "SELECT COUNT(*) FROM account_pending_registrations WHERE id = :id"
                ),
                {"id": pending_id},
            ).scalar_one() == 1
    finally:
        engine.dispose()


def test_expand_backfill_refuses_casefold_collision_without_mutating_users(
    tmp_path,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'collision-refusal.db').as_posix()}"
    config = alembic_config(database_url)
    command.upgrade(config, PARENT_REVISION)
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO "user"
                        (id, username, hashed_password, is_active, is_superuser,
                         is_verified, auth_version)
                    VALUES
                        ('00000000000040008000000000000601', 'Straße', 'hash-a',
                         true, false, true, 3),
                        ('00000000000040008000000000000602', 'STRASSE', 'hash-b',
                         true, false, false, 4)
                    """
                )
            )

        with pytest.raises(RuntimeError, match="category=USERNAME_USERNAME"):
            command.upgrade(config, "head")

        with engine.connect() as connection:
            users = connection.execute(
                text(
                    "SELECT username, hashed_password, is_verified, auth_version "
                    "FROM \"user\" ORDER BY hashed_password"
                )
            ).all()
        assert users == [
            ("Straße", "hash-a", True, 3),
            ("STRASSE", "hash-b", False, 4),
        ]
        assert "account_pending_registrations" not in inspect(engine).get_table_names()
        assert "account_origin" not in {
            column["name"] for column in inspect(engine).get_columns("user")
        }
    finally:
        engine.dispose()
