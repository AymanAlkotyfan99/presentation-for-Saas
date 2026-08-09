"""add nullable user preferred locale

Revision ID: f3a5c7e9b1d2
Revises: e1b3c5d7f9a2
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f3a5c7e9b1d2"
down_revision: str | None = "e1b3c5d7f9a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "user" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("user")}
    if "preferred_locale" in columns:
        return
    with op.batch_alter_table("user") as batch:
        batch.add_column(sa.Column("preferred_locale", sa.String(length=8), nullable=True))
        batch.create_check_constraint(
            "ck_user_preferred_locale",
            "preferred_locale IS NULL OR preferred_locale IN ('en', 'ar')",
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "user" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("user")}
    if "preferred_locale" not in columns:
        return
    with op.batch_alter_table("user") as batch:
        batch.drop_constraint("ck_user_preferred_locale", type_="check")
        batch.drop_column("preferred_locale")
