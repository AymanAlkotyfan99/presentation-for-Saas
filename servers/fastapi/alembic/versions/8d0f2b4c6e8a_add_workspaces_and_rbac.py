"""add workspace tenancy, RBAC, invitations, credentials, and audit

Revision ID: 8d0f2b4c6e8a
Revises: 7c9e1a3b5d6f
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "8d0f2b4c6e8a"
down_revision: str | None = "7c9e1a3b5d6f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLE_VALUES = ("OWNER", "ADMIN", "EDITOR", "VIEWER")


def _workspace_column(table: str) -> None:
    # Partial historical fixtures can retain foreign keys whose referenced
    # aggregate table is intentionally absent. Avoid resolving those unrelated
    # targets while SQLite performs its copy-and-move batch alteration.
    with op.batch_alter_table(table, reflect_kwargs={"resolve_fks": False}) as batch:
        batch.add_column(sa.Column("workspace_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(f"fk_{table}_workspace_id", "workspaces", ["workspace_id"], ["id"], ondelete="CASCADE")
        batch.create_index(f"ix_{table}_workspace_id", ["workspace_id"], unique=False)


def _drop_revision_immutability(tables: set[str]) -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        for table in ("presentation_revisions", "presentation_revision_patches"):
            if table in tables:
                op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable ON {table}")
    elif dialect == "sqlite":
        for table in ("presentation_revisions", "presentation_revision_patches"):
            if table in tables:
                op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_update_immutable")
                op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_delete_immutable")


def _restore_revision_immutability(tables: set[str]) -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        for table in ("presentation_revisions", "presentation_revision_patches"):
            if table in tables:
                op.execute(f"CREATE TRIGGER trg_{table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION bayanly_revisions_are_immutable()")
    elif dialect == "sqlite":
        for table in ("presentation_revisions", "presentation_revision_patches"):
            if table in tables:
                op.execute(f"CREATE TRIGGER trg_{table}_update_immutable BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, 'presentation revision rows are immutable'); END")
                op.execute(f"CREATE TRIGGER trg_{table}_delete_immutable BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, 'presentation revision rows are immutable'); END")


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())
    existing_columns = {
        table: {column["name"] for column in inspector.get_columns(table)}
        for table in existing_tables
    }
    role = sa.Enum(*ROLE_VALUES, name="workspace_role", native_enum=False, create_constraint=True)
    invitation_role = sa.Enum(*ROLE_VALUES, name="invitation_role", native_enum=False, create_constraint=True)
    membership_status = sa.Enum("ACTIVE", "SUSPENDED", name="membership_status", native_enum=False, create_constraint=True)
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("is_personal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("personal_owner_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("length(name) >= 1 AND length(name) <= 160", name="ck_workspaces_name"),
        sa.ForeignKeyConstraint(["personal_owner_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("personal_owner_id", name="uq_workspaces_personal_owner"),
    )
    op.create_index("ix_workspaces_created_by", "workspaces", ["created_by"])
    op.create_table(
        "memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", role, nullable=False),
        sa.Column("status", membership_status, nullable=False, server_default="ACTIVE"),
        sa.Column("permission_overrides", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_memberships_workspace_user"),
    )
    op.create_index("ix_memberships_user_status", "memberships", ["user_id", "status"])
    op.create_index("ix_memberships_workspace_role", "memberships", ["workspace_id", "role"])
    op.create_table(
        "invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("invited_identity", sa.String(128), nullable=False),
        sa.Column("role", invitation_role, nullable=False),
        sa.Column("token_digest", sa.String(64), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_by", sa.Uuid(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("send_count", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("length(token_digest) = 64", name="ck_invitations_token_digest"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["accepted_by"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_digest", name="uq_invitations_token_digest"),
    )
    op.create_index("ix_invitations_workspace_state", "invitations", ["workspace_id", "accepted_at", "revoked_at", "expires_at"])
    op.create_index("ix_invitations_identity", "invitations", ["workspace_id", "invited_identity"])
    op.create_table(
        "service_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "name", name="uq_service_accounts_workspace_name"),
    )
    op.create_index("ix_service_accounts_workspace_id", "service_accounts", ["workspace_id"])
    op.create_table(
        "api_credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("service_account_id", sa.Uuid(), nullable=False),
        sa.Column("key_prefix", sa.String(64), nullable=False),
        sa.Column("secret_digest", sa.String(64), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("length(secret_digest) = 64", name="ck_api_credentials_secret_digest"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_account_id"], ["service_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_prefix", name="uq_api_credentials_key_prefix"),
    )
    op.create_index("ix_api_credentials_service_account_id", "api_credentials", ["service_account_id"])
    op.create_index("ix_api_credentials_workspace_active", "api_credentials", ["workspace_id", "revoked_at", "expires_at"])
    op.create_table(
        "api_credential_scopes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("credential_id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["credential_id"], ["api_credentials.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("credential_id", "scope", name="uq_api_credential_scopes_value"),
    )
    op.create_index("ix_api_credential_scopes_credential_id", "api_credential_scopes", ["credential_id"])
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor_service_account_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("subject_type", sa.String(64), nullable=False),
        sa.Column("subject_id", sa.String(128), nullable=False),
        sa.Column("safe_metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_service_account_id"], ["service_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_workspace_created", "audit_events", ["workspace_id", "created_at"])

    owned_tables = (
        "presentations", "presentation_documents", "presentation_revisions",
        "presentation_revision_patches", "slides", "imageasset", "templates",
        "template_v2", "async_tasks", "async_presentation_generation_tasks",
        "chat_history_messages", "access_tokens", "webhook_subscriptions",
        "presentation_layout_codes", "template_create_infos",
    )
    present_owned_tables = tuple(table for table in owned_tables if table in existing_tables)
    _drop_revision_immutability(existing_tables)
    for table in present_owned_tables:
        _workspace_column(table)

    if "async_tasks" in existing_tables:
        with op.batch_alter_table("async_tasks") as batch:
            batch.add_column(sa.Column("resource_id", sa.String(128), nullable=True))
            batch.create_index("ix_async_tasks_resource_id", ["resource_id"], unique=False)
        async_columns = existing_columns["async_tasks"]
        if {"actor_id", "owner_id"} <= async_columns:
            op.execute("UPDATE async_tasks SET actor_id = owner_id WHERE actor_id IS NULL AND owner_id IS NOT NULL")
        resource_source = "CAST(presentation_id AS VARCHAR(128))" if "presentation_id" in async_columns else "id"
        op.execute(f"UPDATE async_tasks SET resource_id = COALESCE({resource_source}, id) WHERE resource_id IS NULL")
    if "async_presentation_generation_tasks" in existing_tables:
        with op.batch_alter_table("async_presentation_generation_tasks") as batch:
            batch.add_column(sa.Column("actor_id", sa.Uuid(), nullable=True))
            batch.add_column(sa.Column("presentation_id", sa.Uuid(), nullable=True))
            batch.add_column(sa.Column("resource_id", sa.String(128), nullable=True))
            batch.create_foreign_key("fk_async_presentation_generation_tasks_actor_id", "user", ["actor_id"], ["id"], ondelete="SET NULL")
            if "presentations" in existing_tables:
                batch.create_foreign_key("fk_async_presentation_generation_tasks_presentation_id", "presentations", ["presentation_id"], ["id"], ondelete="CASCADE")
            batch.create_index("ix_async_presentation_generation_tasks_actor_id", ["actor_id"], unique=False)
            batch.create_index("ix_async_presentation_generation_tasks_presentation_id", ["presentation_id"], unique=False)
            batch.create_index("ix_async_presentation_generation_tasks_resource_id", ["resource_id"], unique=False)
        if "owner_id" in existing_columns["async_presentation_generation_tasks"]:
            op.execute("UPDATE async_presentation_generation_tasks SET actor_id = owner_id WHERE actor_id IS NULL AND owner_id IS NOT NULL")
        op.execute("UPDATE async_presentation_generation_tasks SET resource_id = id WHERE resource_id IS NULL")

    # Portable and idempotent: the user UUID is the personal-workspace UUID.
    if "user" in existing_tables:
        op.execute("""
        INSERT INTO workspaces (id, name, is_personal, personal_owner_id, created_by, created_at, updated_at)
        SELECT u.id, u.username, TRUE, u.id, u.id, COALESCE(u.created_at, CURRENT_TIMESTAMP), CURRENT_TIMESTAMP
          FROM "user" u
         WHERE NOT EXISTS (SELECT 1 FROM workspaces w WHERE w.personal_owner_id = u.id)
        """)
        op.execute("""
        INSERT INTO memberships (id, workspace_id, user_id, role, status, permission_overrides, created_at, updated_at)
        SELECT u.id, u.id, u.id, 'OWNER', 'ACTIVE', '[]', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
          FROM "user" u
         WHERE NOT EXISTS (SELECT 1 FROM memberships m WHERE m.workspace_id = u.id AND m.user_id = u.id)
        """)
    for table in present_owned_tables:
        identity = "user_id" if table == "access_tokens" else "owner_id"
        if identity in existing_columns[table]:
            op.execute(f"UPDATE {table} SET workspace_id = {identity} WHERE workspace_id IS NULL AND {identity} IS NOT NULL")

    # Children follow their presentation even if historical owner metadata was
    # imperfect, preserving one tenant boundary for the entire revision graph.
    if "presentations" in existing_tables:
        child_bindings = {
            "presentation_documents": "presentation_id",
            "presentation_revisions": "presentation_id",
            "presentation_revision_patches": "presentation_id",
            "chat_history_messages": "presentation_id",
            "async_tasks": "presentation_id",
        }
        for table, column in child_bindings.items():
            if table in existing_tables and column in existing_columns[table]:
                op.execute(f"UPDATE {table} SET workspace_id = (SELECT p.workspace_id FROM presentations p WHERE p.id = {table}.{column}) WHERE {column} IS NOT NULL")
        if "slides" in existing_tables and "presentation" in existing_columns["slides"]:
            op.execute("UPDATE slides SET workspace_id = (SELECT p.workspace_id FROM presentations p WHERE p.id = slides.presentation) WHERE presentation IS NOT NULL")
    _restore_revision_immutability(existing_tables)

    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("""CREATE OR REPLACE FUNCTION bayanly_audit_is_append_only() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'audit events are append-only'; END; $$""")
        op.execute("CREATE TRIGGER trg_audit_events_immutable BEFORE UPDATE OR DELETE ON audit_events FOR EACH ROW EXECUTE FUNCTION bayanly_audit_is_append_only()")
    elif dialect == "sqlite":
        op.execute("CREATE TRIGGER trg_audit_events_immutable BEFORE UPDATE ON audit_events BEGIN SELECT RAISE(ABORT, 'audit events are append-only'); END")
        op.execute("CREATE TRIGGER trg_audit_events_no_delete BEFORE DELETE ON audit_events BEGIN SELECT RAISE(ABORT, 'audit events are append-only'); END")


def downgrade() -> None:
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_audit_events_immutable ON audit_events")
        op.execute("DROP FUNCTION IF EXISTS bayanly_audit_is_append_only()")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS trg_audit_events_immutable")
        op.execute("DROP TRIGGER IF EXISTS trg_audit_events_no_delete")
    if "async_presentation_generation_tasks" in existing_tables:
        with op.batch_alter_table("async_presentation_generation_tasks") as batch:
            batch.drop_index("ix_async_presentation_generation_tasks_resource_id")
            batch.drop_index("ix_async_presentation_generation_tasks_presentation_id")
            batch.drop_index("ix_async_presentation_generation_tasks_actor_id")
            if "presentations" in existing_tables:
                batch.drop_constraint("fk_async_presentation_generation_tasks_presentation_id", type_="foreignkey")
            batch.drop_constraint("fk_async_presentation_generation_tasks_actor_id", type_="foreignkey")
            batch.drop_column("resource_id")
            batch.drop_column("presentation_id")
            batch.drop_column("actor_id")
    if "async_tasks" in existing_tables:
        with op.batch_alter_table("async_tasks") as batch:
            batch.drop_index("ix_async_tasks_resource_id")
            batch.drop_column("resource_id")
    owned_tables = (
        "template_create_infos", "presentation_layout_codes", "webhook_subscriptions",
        "access_tokens", "chat_history_messages", "async_presentation_generation_tasks",
        "async_tasks", "template_v2", "templates", "imageasset", "slides",
        "presentation_revision_patches", "presentation_revisions",
        "presentation_documents", "presentations",
    )
    present_owned_tables = tuple(table for table in owned_tables if table in existing_tables)
    _drop_revision_immutability(existing_tables)
    for table in present_owned_tables:
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_workspace_id")
            batch.drop_constraint(f"fk_{table}_workspace_id", type_="foreignkey")
            batch.drop_column("workspace_id")
    _restore_revision_immutability(existing_tables)
    op.drop_table("audit_events")
    op.drop_table("api_credential_scopes")
    op.drop_table("api_credentials")
    op.drop_table("service_accounts")
    op.drop_table("invitations")
    op.drop_table("memberships")
    op.drop_table("workspaces")
