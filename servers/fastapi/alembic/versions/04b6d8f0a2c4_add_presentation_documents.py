"""add canonical presentation documents

Revision ID: 04b6d8f0a2c4
Revises: f3a5c7e9b1d2
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "04b6d8f0a2c4"
down_revision: str | None = "f3a5c7e9b1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

document_json = sa.JSON(none_as_null=True).with_variant(
    postgresql.JSONB(none_as_null=True), "postgresql"
)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "presentation_documents" in inspector.get_table_names():
        return
    op.create_table(
        "presentation_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("presentation_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("document", document_json, nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "conversion_status",
            sa.Enum(
                "NOT_STARTED", "PENDING", "CONVERTING", "CONVERTED", "FAILED",
                "UNSUPPORTED", "NEEDS_REVIEW",
                name="canonical_conversion_status", native_enum=False, create_constraint=True,
            ),
            nullable=False,
            server_default="NOT_STARTED",
        ),
        sa.Column("conversion_error_code", sa.String(length=128), nullable=True),
        sa.Column("conversion_error_details", sa.JSON(), nullable=True),
        sa.Column("legacy_source_version", sa.String(length=64), nullable=True),
        sa.Column("conversion_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("asset_mappings", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("revision >= 1", name="ck_presentation_documents_revision"),
        sa.CheckConstraint(
            "conversion_attempts >= 0 AND conversion_attempts <= 3",
            name="ck_presentation_documents_attempts",
        ),
        sa.CheckConstraint(
            "schema_version = '1.0.0'",
            name="ck_presentation_documents_schema_version",
        ),
        sa.CheckConstraint(
            "(document IS NULL AND checksum IS NULL) OR "
            "(document IS NOT NULL AND checksum IS NOT NULL AND length(checksum) = 64)",
            name="ck_presentation_documents_payload_checksum",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["presentation_id"], ["presentations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("presentation_id", name="uq_presentation_documents_presentation_id"),
    )
    op.create_index("ix_presentation_documents_checksum", "presentation_documents", ["checksum"], unique=False)
    op.create_index("ix_presentation_documents_owner_id", "presentation_documents", ["owner_id"], unique=False)
    op.create_index("ix_presentation_documents_conversion_status", "presentation_documents", ["conversion_status"], unique=False)
    op.create_index("ix_presentation_documents_owner_status", "presentation_documents", ["owner_id", "conversion_status"], unique=False)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "presentation_documents" in inspector.get_table_names():
        op.drop_table("presentation_documents")
