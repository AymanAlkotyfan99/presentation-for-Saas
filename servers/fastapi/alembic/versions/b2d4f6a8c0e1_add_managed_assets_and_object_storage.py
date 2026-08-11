"""add managed assets, object versions, uploads and references

Revision ID: b2d4f6a8c0e1
Revises: a1c3e5f7b9d2
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "b2d4f6a8c0e1"
down_revision: str | None = "a1c3e5f7b9d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("creator_service_account_id", sa.Uuid(), nullable=True),
        sa.Column("storage_provider", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("declared_mime", sa.String(128), nullable=True),
        sa.Column("detected_mime", sa.String(128), nullable=True),
        sa.Column("state", sa.String(32), nullable=False, server_default="UPLOADING"),
        sa.Column("malware_scan_status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("retention_class", sa.String(32), nullable=False, server_default="WORKSPACE"),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("accessibility_metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("size_bytes >= 0", name="ck_assets_size"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["creator_service_account_id"], ["service_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_assets_storage_key"),
    )
    op.create_index("ix_assets_workspace_created", "assets", ["workspace_id", "created_at"])
    op.create_index("ix_assets_workspace_state", "assets", ["workspace_id", "state"])
    op.create_index("ix_assets_checksum", "assets", ["workspace_id", "checksum_sha256"])

    op.create_table(
        "object_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("storage_provider", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("detected_mime", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id", "version_number", name="uq_object_versions_asset_version"),
        sa.UniqueConstraint("storage_provider", "storage_key", name="uq_object_versions_storage_key"),
    )
    op.create_index("ix_object_versions_workspace_asset", "object_versions", ["workspace_id", "asset_id"])

    op.create_table(
        "upload_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor_service_account_id", sa.Uuid(), nullable=True),
        sa.Column("storage_provider", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("target_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("provider_upload_id", sa.String(512), nullable=True),
        sa.Column("state", sa.String(32), nullable=False, server_default="CREATED"),
        sa.Column("expected_size", sa.Integer(), nullable=False),
        sa.Column("expected_checksum_sha256", sa.String(64), nullable=True),
        sa.Column("declared_mime", sa.String(128), nullable=False),
        sa.Column("multipart", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("completed_parts", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("aborted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_service_account_id"], ["service_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_upload_sessions_workspace_state", "upload_sessions", ["workspace_id", "state", "expires_at"])
    op.create_index("ix_upload_sessions_asset", "upload_sessions", ["asset_id", "created_at"])

    op.create_table(
        "asset_references",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(128), nullable=False),
        sa.Column("reference_type", sa.String(64), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "asset_id", "resource_type", "resource_id", "reference_type", name="uq_asset_reference_binding"),
    )
    op.create_index("ix_asset_references_resource", "asset_references", ["workspace_id", "resource_type", "resource_id"])
    op.create_index("ix_asset_references_asset", "asset_references", ["workspace_id", "asset_id"])

    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "imageasset" in tables and "asset_id" not in {item["name"] for item in inspector.get_columns("imageasset")}:
        with op.batch_alter_table("imageasset", reflect_kwargs={"resolve_fks": False}) as batch:
            batch.add_column(sa.Column("asset_id", sa.Uuid(), nullable=True))
            batch.create_foreign_key("fk_imageasset_asset_id", "assets", ["asset_id"], ["id"], ondelete="SET NULL")
            batch.create_index("ix_imageasset_asset_id", ["asset_id"])
    if "presentations" in tables and "file_asset_ids" not in {item["name"] for item in inspector.get_columns("presentations")}:
        with op.batch_alter_table("presentations", reflect_kwargs={"resolve_fks": False}) as batch:
            batch.add_column(sa.Column("file_asset_ids", sa.JSON(), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "presentations" in tables and "file_asset_ids" in {item["name"] for item in inspector.get_columns("presentations")}:
        with op.batch_alter_table("presentations", reflect_kwargs={"resolve_fks": False}) as batch:
            batch.drop_column("file_asset_ids")
    if "imageasset" in tables and "asset_id" in {item["name"] for item in inspector.get_columns("imageasset")}:
        with op.batch_alter_table("imageasset", reflect_kwargs={"resolve_fks": False}) as batch:
            batch.drop_index("ix_imageasset_asset_id")
            batch.drop_constraint("fk_imageasset_asset_id", type_="foreignkey")
            batch.drop_column("asset_id")
    op.drop_index("ix_asset_references_asset", table_name="asset_references")
    op.drop_index("ix_asset_references_resource", table_name="asset_references")
    op.drop_table("asset_references")
    op.drop_index("ix_upload_sessions_asset", table_name="upload_sessions")
    op.drop_index("ix_upload_sessions_workspace_state", table_name="upload_sessions")
    op.drop_table("upload_sessions")
    op.drop_index("ix_object_versions_workspace_asset", table_name="object_versions")
    op.drop_table("object_versions")
    op.drop_index("ix_assets_checksum", table_name="assets")
    op.drop_index("ix_assets_workspace_state", table_name="assets")
    op.drop_index("ix_assets_workspace_created", table_name="assets")
    op.drop_table("assets")
