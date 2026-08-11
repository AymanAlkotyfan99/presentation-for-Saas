"""add provider registry, encrypted secrets, routing and shared circuit state

Revision ID: c3e5f7a9b1d2
Revises: b2d4f6a8c0e1
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c3e5f7a9b1d2"
down_revision: str | None = "b2d4f6a8c0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("adapter_id", sa.String(128), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("default_model", sa.String(160), nullable=True),
        sa.Column("safe_config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("region_policy_status", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("emergency_disabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "name", name="uq_provider_accounts_workspace_name"),
    )
    op.create_index("ix_provider_accounts_workspace_adapter", "provider_accounts", ["workspace_id", "adapter_id"])

    op.create_table(
        "encrypted_provider_secrets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_account_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("nonce", sa.String(64), nullable=False),
        sa.Column("encrypted_data_key", sa.Text(), nullable=False),
        sa.Column("data_key_nonce", sa.String(64), nullable=False),
        sa.Column("master_key_version", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["provider_account_id"], ["provider_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_account_id", "name", "version", name="uq_provider_secret_version"),
    )
    op.create_index("ix_provider_secrets_active", "encrypted_provider_secrets", ["provider_account_id", "name", "deleted_at", "version"])

    op.create_table(
        "provider_capabilities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_account_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("family", sa.String(16), nullable=False),
        sa.Column("model", sa.String(160), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["provider_account_id"], ["provider_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_account_id", "family", "model", name="uq_provider_capability_model"),
    )
    op.create_index("ix_provider_capabilities_workspace_family", "provider_capabilities", ["workspace_id", "family", "enabled"])

    op.create_table(
        "provider_health",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_account_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("safe_error_code", sa.String(96), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["provider_account_id"], ["provider_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_account_id", name="uq_provider_health_account"),
    )

    op.create_table(
        "routing_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("family", sa.String(16), nullable=False),
        sa.Column("priority_account_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("allow_fallback", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("max_fallbacks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("region_rules", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("plan_rules", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("max_fallbacks >= 0 AND max_fallbacks <= 3", name="ck_routing_policy_fallbacks"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "family", name="uq_routing_policy_workspace_family"),
    )

    op.create_table(
        "provider_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("provider_account_id", sa.Uuid(), nullable=False),
        sa.Column("adapter_id", sa.String(128), nullable=False),
        sa.Column("family", sa.String(16), nullable=False),
        sa.Column("model", sa.String(160), nullable=False),
        sa.Column("routing_policy_id", sa.Uuid(), nullable=True),
        sa.Column("routing_policy_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("safe_config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("region_decision", sa.String(32), nullable=False),
        sa.Column("fallback_reason", sa.String(96), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["provider_account_id"], ["provider_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["routing_policy_id"], ["routing_policies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_provider_snapshots_workspace_created", "provider_snapshots", ["workspace_id", "created_at"])

    op.create_table(
        "provider_circuits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_account_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("family", sa.String(16), nullable=False),
        sa.Column("model", sa.String(160), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="CLOSED"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("opened_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("half_open_probe_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["provider_account_id"], ["provider_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_account_id", "family", "model", name="uq_provider_circuit_scope"),
    )
    op.create_index("ix_provider_circuits_workspace_state", "provider_circuits", ["workspace_id", "state"])

    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("CREATE FUNCTION reject_provider_snapshot_mutation() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'provider snapshots are immutable'; END; $$ LANGUAGE plpgsql")
        op.execute("CREATE TRIGGER provider_snapshots_immutable BEFORE UPDATE OR DELETE ON provider_snapshots FOR EACH ROW EXECUTE FUNCTION reject_provider_snapshot_mutation()")
    elif dialect == "sqlite":
        op.execute("CREATE TRIGGER provider_snapshots_no_update BEFORE UPDATE ON provider_snapshots BEGIN SELECT RAISE(ABORT, 'provider snapshots are immutable'); END")
        op.execute("CREATE TRIGGER provider_snapshots_no_delete BEFORE DELETE ON provider_snapshots BEGIN SELECT RAISE(ABORT, 'provider snapshots are immutable'); END")


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS provider_snapshots_immutable ON provider_snapshots")
        op.execute("DROP FUNCTION IF EXISTS reject_provider_snapshot_mutation")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS provider_snapshots_no_update")
        op.execute("DROP TRIGGER IF EXISTS provider_snapshots_no_delete")
    op.drop_index("ix_provider_circuits_workspace_state", table_name="provider_circuits")
    op.drop_table("provider_circuits")
    op.drop_index("ix_provider_snapshots_workspace_created", table_name="provider_snapshots")
    op.drop_table("provider_snapshots")
    op.drop_table("routing_policies")
    op.drop_table("provider_health")
    op.drop_index("ix_provider_capabilities_workspace_family", table_name="provider_capabilities")
    op.drop_table("provider_capabilities")
    op.drop_index("ix_provider_secrets_active", table_name="encrypted_provider_secrets")
    op.drop_table("encrypted_provider_secrets")
    op.drop_index("ix_provider_accounts_workspace_adapter", table_name="provider_accounts")
    op.drop_table("provider_accounts")
