"""add immutable presentation revisions and stale-job pins

Revision ID: 7c9e1a3b5d6f
Revises: 04b6d8f0a2c4
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "7c9e1a3b5d6f"
down_revision: str | None = "04b6d8f0a2c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

revision_json = sa.JSON(none_as_null=True).with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


def _immutable_triggers(tables: set[str]) -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("""
            CREATE OR REPLACE FUNCTION bayanly_revisions_are_immutable()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'presentation revision rows are immutable'; END; $$
        """)
        for table in ("presentation_revisions", "presentation_revision_patches"):
            if table in tables:
                op.execute(f"CREATE TRIGGER trg_{table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION bayanly_revisions_are_immutable()")
    elif dialect == "sqlite":
        for table in ("presentation_revisions", "presentation_revision_patches"):
            if table in tables:
                op.execute(f"CREATE TRIGGER trg_{table}_update_immutable BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, 'presentation revision rows are immutable'); END")
                op.execute(f"CREATE TRIGGER trg_{table}_delete_immutable BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, 'presentation revision rows are immutable'); END")


def upgrade() -> None:
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "presentations" not in existing_tables:
        # Historical migration tests can stamp a revision onto a deliberately
        # partial schema. Without the aggregate root there is no revision graph.
        return

    with op.batch_alter_table("presentations") as batch:
        batch.add_column(sa.Column("current_revision", sa.Integer(), nullable=False, server_default="0"))
        batch.create_check_constraint("ck_presentations_current_revision", "current_revision >= 0")
    if "async_tasks" in existing_tables:
        with op.batch_alter_table("async_tasks") as batch:
            batch.add_column(sa.Column("presentation_id", sa.Uuid(), nullable=True))
            batch.add_column(sa.Column("source_revision", sa.Integer(), nullable=True))
            batch.add_column(sa.Column("actor_id", sa.Uuid(), nullable=True))
            batch.create_foreign_key("fk_async_tasks_presentation_id", "presentations", ["presentation_id"], ["id"], ondelete="CASCADE")
            batch.create_foreign_key("fk_async_tasks_actor_id", "user", ["actor_id"], ["id"], ondelete="SET NULL")
            batch.create_index("ix_async_tasks_presentation_id", ["presentation_id"], unique=False)

    op.create_table(
        "presentation_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("presentation_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("parent_revision", sa.Integer(), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("snapshot_document", revision_json, nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="command"),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("restored_from_revision", sa.Integer(), nullable=True),
        sa.Column("retention_class", sa.String(32), nullable=False, server_default="standard"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("revision >= 1", name="ck_presentation_revisions_number"),
        sa.CheckConstraint("parent_revision IS NULL OR parent_revision >= 1", name="ck_presentation_revisions_parent"),
        sa.CheckConstraint("length(checksum) = 64", name="ck_presentation_revisions_checksum"),
        sa.ForeignKeyConstraint(["presentation_id"], ["presentations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("presentation_id", "revision", name="uq_presentation_revisions_number"),
    )
    op.create_index("ix_presentation_revisions_owner_id", "presentation_revisions", ["owner_id"])
    op.create_index("ix_presentation_revisions_owner_presentation", "presentation_revisions", ["owner_id", "presentation_id"])

    op.create_table(
        "presentation_revision_patches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("presentation_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("actor_scope", sa.String(128), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_checksum", sa.String(64), nullable=False),
        sa.Column("commands", revision_json, nullable=False),
        sa.Column("command_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("revision >= 1 AND base_revision >= 0", name="ck_presentation_revision_patches_numbers"),
        sa.CheckConstraint("command_count >= 0 AND command_count <= 500", name="ck_presentation_revision_patches_command_count"),
        sa.CheckConstraint("length(request_checksum) = 64", name="ck_presentation_revision_patches_checksum"),
        sa.ForeignKeyConstraint(["presentation_id"], ["presentations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("presentation_id", "revision", name="uq_presentation_revision_patches_number"),
        sa.UniqueConstraint("presentation_id", "actor_scope", "idempotency_key", name="uq_presentation_revision_patches_idempotency"),
    )
    op.create_index("ix_presentation_revision_patches_owner_id", "presentation_revision_patches", ["owner_id"])
    op.create_index("ix_presentation_revision_patches_owner_presentation", "presentation_revision_patches", ["owner_id", "presentation_id"])

    # Existing canonical snapshots become anchors without materializing legacy
    # slide data or copying through application memory. presentation_id is a
    # stable UUID and safely doubles as the seed revision row's primary key.
    if "presentation_documents" in existing_tables:
        op.execute("""
            INSERT INTO presentation_revisions
              (id, presentation_id, owner_id, revision, parent_revision, checksum,
               snapshot_document, source, actor_id, retention_class, created_at)
            SELECT pd.presentation_id, pd.presentation_id, pd.owner_id, pd.revision,
                   NULL, pd.checksum, pd.document, 'canonical-bootstrap', pd.owner_id,
                   'anchor', pd.created_at
              FROM presentation_documents pd
             WHERE pd.document IS NOT NULL AND pd.checksum IS NOT NULL
        """)
        op.execute("""
            UPDATE presentations
               SET current_revision = COALESCE(
                   (SELECT pd.revision FROM presentation_documents pd
                     WHERE pd.presentation_id = presentations.id
                       AND pd.document IS NOT NULL), 0)
        """)
    _immutable_triggers({"presentation_revisions", "presentation_revision_patches"})


def downgrade() -> None:
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        for table in ("presentation_revisions", "presentation_revision_patches"):
            if table in existing_tables:
                op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable ON {table}")
        op.execute("DROP FUNCTION IF EXISTS bayanly_revisions_are_immutable()")
    elif dialect == "sqlite":
        for table in ("presentation_revisions", "presentation_revision_patches"):
            if table in existing_tables:
                op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_update_immutable")
                op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_delete_immutable")
    if "presentation_revision_patches" in existing_tables:
        op.drop_table("presentation_revision_patches")
    if "presentation_revisions" in existing_tables:
        op.drop_table("presentation_revisions")
    if "async_tasks" in existing_tables and "presentation_id" in {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("async_tasks")
    }:
        with op.batch_alter_table("async_tasks") as batch:
            batch.drop_index("ix_async_tasks_presentation_id")
            batch.drop_constraint("fk_async_tasks_actor_id", type_="foreignkey")
            batch.drop_constraint("fk_async_tasks_presentation_id", type_="foreignkey")
            batch.drop_column("actor_id")
            batch.drop_column("source_revision")
            batch.drop_column("presentation_id")
    if "presentations" in existing_tables and "current_revision" in {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("presentations")
    }:
        with op.batch_alter_table("presentations") as batch:
            batch.drop_constraint("ck_presentations_current_revision", type_="check")
            batch.drop_column("current_revision")
