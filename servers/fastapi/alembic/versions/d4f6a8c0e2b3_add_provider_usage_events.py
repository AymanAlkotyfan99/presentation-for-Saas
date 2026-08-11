"""add append-only provider usage and cost hooks

Revision ID: d4f6a8c0e2b3
Revises: c3e5f7a9b1d2
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "d4f6a8c0e2b3"
down_revision: str | None = "c3e5f7a9b1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_usage_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("provider_account_id", sa.Uuid(), nullable=False),
        sa.Column("provider_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("adapter_id", sa.String(128), nullable=False),
        sa.Column("family", sa.String(16), nullable=False),
        sa.Column("model", sa.String(160), nullable=False),
        sa.Column("operation", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("safe_error_code", sa.String(96), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("image_count", sa.Integer(), nullable=True),
        sa.Column("search_count", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("estimated_cost", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("pricing_snapshot_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provider_account_id"], ["provider_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["provider_snapshot_id"], ["provider_snapshots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_provider_usage_workspace_created", "provider_usage_events", ["workspace_id", "created_at"])
    op.create_index("ix_provider_usage_account_created", "provider_usage_events", ["provider_account_id", "created_at"])

    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("CREATE FUNCTION reject_provider_usage_mutation() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'provider usage events are immutable'; END; $$ LANGUAGE plpgsql")
        op.execute("CREATE TRIGGER provider_usage_events_immutable BEFORE UPDATE OR DELETE ON provider_usage_events FOR EACH ROW EXECUTE FUNCTION reject_provider_usage_mutation()")
    elif dialect == "sqlite":
        op.execute("CREATE TRIGGER provider_usage_events_no_update BEFORE UPDATE ON provider_usage_events BEGIN SELECT RAISE(ABORT, 'provider usage events are immutable'); END")
        op.execute("CREATE TRIGGER provider_usage_events_no_delete BEFORE DELETE ON provider_usage_events BEGIN SELECT RAISE(ABORT, 'provider usage events are immutable'); END")


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS provider_usage_events_immutable ON provider_usage_events")
        op.execute("DROP FUNCTION IF EXISTS reject_provider_usage_mutation")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS provider_usage_events_no_update")
        op.execute("DROP TRIGGER IF EXISTS provider_usage_events_no_delete")
    op.drop_index("ix_provider_usage_account_created", table_name="provider_usage_events")
    op.drop_index("ix_provider_usage_workspace_created", table_name="provider_usage_events")
    op.drop_table("provider_usage_events")
