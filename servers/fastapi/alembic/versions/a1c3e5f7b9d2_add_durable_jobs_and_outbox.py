"""add durable jobs, attempts, transactional outbox and consumer inbox

Revision ID: a1c3e5f7b9d2
Revises: 8d0f2b4c6e8a
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "a1c3e5f7b9d2"
down_revision: str | None = "8d0f2b4c6e8a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor_service_account_id", sa.Uuid(), nullable=True),
        sa.Column("operation", sa.String(96), nullable=False),
        sa.Column("queue_class", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_message", sa.String(256), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("payload_schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("result_schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("idempotency_scope", sa.String(192), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("source_revision", sa.Integer(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("lease_owner", sa.String(128), nullable=True),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("parent_trace_id", sa.String(64), nullable=True),
        sa.Column("safe_error_code", sa.String(96), nullable=True),
        sa.Column("safe_error_message", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("progress >= 0 AND progress <= 100", name="ck_jobs_progress"),
        sa.CheckConstraint("attempt_count >= 0 AND max_attempts >= 1", name="ck_jobs_attempts"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_service_account_id"], ["service_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "idempotency_scope", "idempotency_key", name="uq_jobs_workspace_idempotency"),
    )
    op.create_index("ix_jobs_queue_available", "jobs", ["queue_class", "status", "available_at"])
    op.create_index("ix_jobs_workspace_created", "jobs", ["workspace_id", "created_at"])
    op.create_index("ix_jobs_lease", "jobs", ["status", "lease_until"])

    op.create_table(
        "job_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(128), nullable=False),
        sa.Column("lease_token", sa.Uuid(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_class", sa.String(64), nullable=True),
        sa.Column("safe_error_code", sa.String(96), nullable=True),
        sa.Column("safe_error_message", sa.String(512), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "attempt_number", name="uq_job_attempt_number"),
    )
    op.create_index("ix_job_attempts_workspace_job", "job_attempts", ["workspace_id", "job_id"])

    op.create_table(
        "outbox_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("topic", sa.String(96), nullable=False),
        sa.Column("queue_class", sa.String(32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("publish_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(96), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", name="uq_outbox_message_id"),
    )
    op.create_index("ix_outbox_pending", "outbox_messages", ["published_at", "available_at", "created_at"])

    op.create_table(
        "consumer_inbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("consumer_id", sa.String(128), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("consumer_id", "message_id", name="uq_consumer_inbox_delivery"),
    )
    op.create_index("ix_consumer_inbox_workspace_received", "consumer_inbox", ["workspace_id", "received_at"])

    op.create_table(
        "dead_letters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(96), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("safe_error_code", sa.String(96), nullable=False),
        sa.Column("safe_error_message", sa.String(512), nullable=True),
        sa.Column("retry_class", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dead_letters_workspace_created", "dead_letters", ["workspace_id", "created_at"])

    op.create_table(
        "job_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("safe_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_events_workspace_job_id", "job_events", ["workspace_id", "job_id", "id"])

    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "async_tasks" in tables and "durable_job_id" not in {item["name"] for item in inspector.get_columns("async_tasks")}:
        with op.batch_alter_table("async_tasks", reflect_kwargs={"resolve_fks": False}) as batch:
            batch.add_column(sa.Column("durable_job_id", sa.Uuid(), nullable=True))
            batch.create_foreign_key("fk_async_tasks_durable_job_id", "jobs", ["durable_job_id"], ["id"], ondelete="SET NULL")
            batch.create_index("ix_async_tasks_durable_job_id", ["durable_job_id"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "async_tasks" in tables and "durable_job_id" in {item["name"] for item in inspector.get_columns("async_tasks")}:
        with op.batch_alter_table("async_tasks", reflect_kwargs={"resolve_fks": False}) as batch:
            batch.drop_index("ix_async_tasks_durable_job_id")
            batch.drop_constraint("fk_async_tasks_durable_job_id", type_="foreignkey")
            batch.drop_column("durable_job_id")
    op.drop_index("ix_job_events_workspace_job_id", table_name="job_events")
    op.drop_table("job_events")
    op.drop_index("ix_dead_letters_workspace_created", table_name="dead_letters")
    op.drop_table("dead_letters")
    op.drop_index("ix_consumer_inbox_workspace_received", table_name="consumer_inbox")
    op.drop_table("consumer_inbox")
    op.drop_index("ix_outbox_pending", table_name="outbox_messages")
    op.drop_table("outbox_messages")
    op.drop_index("ix_job_attempts_workspace_job", table_name="job_attempts")
    op.drop_table("job_attempts")
    op.drop_index("ix_jobs_lease", table_name="jobs")
    op.drop_index("ix_jobs_workspace_created", table_name="jobs")
    op.drop_index("ix_jobs_queue_available", table_name="jobs")
    op.drop_table("jobs")
