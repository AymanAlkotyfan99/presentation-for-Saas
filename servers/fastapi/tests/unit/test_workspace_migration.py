from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError
import pytest


SPRINT_6_REVISION = "7c9e1a3b5d6f"
SPRINT_7_REVISION = "8d0f2b4c6e8a"
CURRENT_PLATFORM_REVISION = "d4f6a8c0e2b3"
USER_ID = "00000000000040008000000000000001"
PRESENTATION_ID = "00000000000040008000000000000010"
REVISION_ID = "00000000000040008000000000000011"


def configuration(database_url: str) -> Config:
    root = Path(__file__).resolve().parents[2]
    config = Config()
    config.set_main_option("script_location", str(root / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_workspace_migration_backfill_is_repeatable_and_audit_is_append_only(tmp_path):
    database_url = f"sqlite:///{(tmp_path / 'workspace-migration.db').as_posix()}"
    config = configuration(database_url)
    command.upgrade(config, SPRINT_6_REVISION)
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO user (id, username, hashed_password, is_active, is_superuser, is_verified, auth_version) "
            "VALUES (:id, :username, :password, true, false, true, 1)"
        ), {"id": USER_ID, "username": "migrated-user", "password": "hash"})
        connection.execute(text(
            "INSERT INTO presentations (id, owner_id, version, content, n_slides, language, created_at, updated_at, current_revision) "
            "VALUES (:id, :owner, 'v2-standard', 'legacy', 1, 'en', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)"
        ), {"id": PRESENTATION_ID, "owner": USER_ID})
        connection.execute(text(
            "INSERT INTO presentation_revisions "
            "(id, presentation_id, owner_id, revision, parent_revision, checksum, snapshot_document, source, actor_id, restored_from_revision, retention_class, created_at) "
            "VALUES (:id, :presentation, :owner, 1, NULL, :checksum, NULL, 'test', :owner, NULL, 'anchor', CURRENT_TIMESTAMP)"
        ), {"id": REVISION_ID, "presentation": PRESENTATION_ID, "owner": USER_ID, "checksum": "a" * 64})

    command.upgrade(config, "head")
    inspector = inspect(engine)
    assert {
        "workspaces", "memberships", "invitations", "service_accounts",
        "api_credentials", "api_credential_scopes", "audit_events",
    }.issubset(inspector.get_table_names())
    assert all("workspace_id" in {column["name"] for column in inspector.get_columns(table)} for table in (
        "presentations", "presentation_documents", "presentation_revisions",
        "presentation_revision_patches", "slides", "imageasset", "templates",
        "template_v2", "async_tasks", "async_presentation_generation_tasks",
        "chat_history_messages", "access_tokens", "webhook_subscriptions",
        "presentation_layout_codes", "template_create_infos",
    ))
    assert "resource_id" in {column["name"] for column in inspector.get_columns("async_tasks")}
    assert {"actor_id", "presentation_id", "resource_id"}.issubset(
        {column["name"] for column in inspector.get_columns("async_presentation_generation_tasks")}
    )
    with engine.begin() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == CURRENT_PLATFORM_REVISION
        assert connection.execute(text("SELECT COUNT(*) FROM workspaces WHERE personal_owner_id = :id"), {"id": USER_ID}).scalar_one() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM memberships WHERE workspace_id = :id AND user_id = :id AND role = 'OWNER' AND status = 'ACTIVE'"), {"id": USER_ID}).scalar_one() == 1
        assert connection.execute(text("SELECT workspace_id FROM presentation_revisions WHERE id = :id"), {"id": REVISION_ID}).scalar_one() == USER_ID
        connection.execute(text(
            "INSERT INTO audit_events (id, workspace_id, actor_id, event_type, subject_type, subject_id, safe_metadata) "
            "VALUES (:event, :workspace, :actor, 'test.event', 'workspace', :subject, '{}')"
        ), {"event": "00000000000040008000000000000002", "workspace": USER_ID, "actor": USER_ID, "subject": USER_ID})
    with pytest.raises(DBAPIError, match="append-only"):
        with engine.begin() as connection:
            connection.execute(text("UPDATE audit_events SET event_type = 'changed'"))
    with pytest.raises(DBAPIError, match="append-only"):
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM audit_events"))
    with pytest.raises(DBAPIError, match="immutable"):
        with engine.begin() as connection:
            connection.execute(text("UPDATE presentation_revisions SET source = 'changed' WHERE id = :id"), {"id": REVISION_ID})
    with pytest.raises(DBAPIError, match="immutable"):
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM presentation_revisions WHERE id = :id"), {"id": REVISION_ID})

    command.downgrade(config, SPRINT_6_REVISION)
    with pytest.raises(DBAPIError, match="immutable"):
        with engine.begin() as connection:
            connection.execute(text("UPDATE presentation_revisions SET source = 'changed' WHERE id = :id"), {"id": REVISION_ID})
    command.upgrade(config, "head")
    with engine.begin() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM workspaces WHERE personal_owner_id = :id"), {"id": USER_ID}).scalar_one() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM memberships WHERE workspace_id = :id AND user_id = :id"), {"id": USER_ID}).scalar_one() == 1
    engine.dispose()
