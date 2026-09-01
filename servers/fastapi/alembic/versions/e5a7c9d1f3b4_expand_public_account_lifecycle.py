"""expand public account lifecycle persistence

Revision ID: e5a7c9d1f3b4
Revises: d4f6a8c0e2b3

This is the additive Sprint 10.10 revision. Strong rollout constraints that
depend on reviewed collision evidence remain owned by the later enforcement
revision; public capabilities stay disabled during this compatibility window.
"""

from __future__ import annotations

from collections.abc import Sequence
import unicodedata

from alembic import op
import sqlalchemy as sa


revision: str = "e5a7c9d1f3b4"
down_revision: str | None = "d4f6a8c0e2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


JOB_CHILD_TABLES = (
    "job_attempts",
    "outbox_messages",
    "consumer_inbox",
    "dead_letters",
    "job_events",
)


def _normalize_username(value: str) -> str:
    return unicodedata.normalize("NFC", value.strip()).casefold()


def _privacy_safe_collision_error(collisions: dict[str, list[str]]) -> RuntimeError:
    ids = sorted({subject_id for values in collisions.values() for subject_id in values})
    return RuntimeError(
        "Account identifier backfill refused: "
        f"category=USERNAME_USERNAME collision_count={len(collisions)} "
        f"affected_user_ids={','.join(ids)}"
    )


def _username_claim_rows() -> list[tuple[object, str]]:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text('SELECT id, username FROM "user" ORDER BY id')
    ).mappings()
    claims: dict[str, list[str]] = {}
    originals: list[tuple[object, str]] = []
    for row in rows:
        normalized = _normalize_username(row["username"])
        if not normalized or len(normalized) > 320:
            raise RuntimeError(
                "Account identifier backfill refused: "
                f"category=INVALID_USERNAME affected_user_ids={row['id']}"
            )
        claims.setdefault(normalized, []).append(str(row["id"]))
        originals.append((row["id"], normalized))
    collisions = {
        normalized: ids for normalized, ids in claims.items() if len(ids) > 1
    }
    if collisions:
        raise _privacy_safe_collision_error(collisions)
    return originals


def _backfill_username_claims() -> None:
    connection = op.get_bind()
    originals = _username_claim_rows()
    for user_id, normalized in originals:
        connection.execute(
            sa.text(
                """
                INSERT INTO account_login_identifiers
                    (normalized_value, user_id, pending_registration_id, kind, created_at)
                VALUES (:normalized, :user_id, NULL, 'USERNAME', CURRENT_TIMESTAMP)
                """
            ),
            {"normalized": normalized, "user_id": user_id},
        )


def _backfill_invitations() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, invited_identity FROM invitations ORDER BY id")
    ).mappings()
    for row in rows:
        normalized = _normalize_username(row["invited_identity"])
        connection.execute(
            sa.text(
                """
                UPDATE invitations
                SET normalized_identity = :normalized,
                    identity_kind = 'USERNAME'
                WHERE id = :invitation_id
                """
            ),
            {"normalized": normalized, "invitation_id": row["id"]},
        )


def _create_lifecycle_audit_immutability() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            "CREATE FUNCTION reject_account_lifecycle_audit_mutation() "
            "RETURNS trigger AS $$ BEGIN RAISE EXCEPTION "
            "'account lifecycle audit events are append-only'; END; $$ LANGUAGE plpgsql"
        )
        op.execute(
            "CREATE TRIGGER account_lifecycle_audit_events_immutable "
            "BEFORE UPDATE OR DELETE ON account_lifecycle_audit_events "
            "FOR EACH ROW EXECUTE FUNCTION reject_account_lifecycle_audit_mutation()"
        )
    elif dialect == "sqlite":
        op.execute(
            "CREATE TRIGGER account_lifecycle_audit_events_no_update "
            "BEFORE UPDATE ON account_lifecycle_audit_events BEGIN SELECT "
            "RAISE(ABORT, 'account lifecycle audit events are append-only'); END"
        )
        op.execute(
            "CREATE TRIGGER account_lifecycle_audit_events_no_delete "
            "BEFORE DELETE ON account_lifecycle_audit_events BEGIN SELECT "
            "RAISE(ABORT, 'account lifecycle audit events are append-only'); END"
        )


def upgrade() -> None:
    # SQLite DDL is not transactional. Refuse ambiguity before making the
    # first additive schema change so a failed backfill cannot strand a
    # partially expanded database.
    _username_claim_rows()

    op.add_column("user", sa.Column("account_origin", sa.String(32), nullable=True))
    op.add_column("user", sa.Column("account_state", sa.String(16), nullable=True))
    op.add_column("user", sa.Column("email_state", sa.String(16), nullable=True))
    op.add_column("user", sa.Column("email_original", sa.String(320), nullable=True))
    op.add_column("user", sa.Column("email_normalized", sa.String(320), nullable=True))
    op.add_column("user", sa.Column("email_generation", sa.Integer(), nullable=True))
    op.add_column(
        "user", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        "ix_user_email_normalized_shadow", "user", ["email_normalized"], unique=False
    )

    op.create_table(
        "account_pending_registrations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("email_original", sa.String(320), nullable=True),
        sa.Column("email_normalized", sa.String(320), nullable=True),
        sa.Column("preferred_locale", sa.String(8), nullable=False),
        sa.Column("claim_generation", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reclaim_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("terminal_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("purge_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_user_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["activated_user_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "activated_user_id", name="uq_account_pending_activated_user"
        ),
    )
    op.create_index(
        "ix_account_pending_reclaim",
        "account_pending_registrations",
        ["state", "reclaim_after", "id"],
    )

    op.create_table(
        "account_login_identifiers",
        sa.Column("normalized_value", sa.String(320), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("pending_registration_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["pending_registration_id"],
            ["account_pending_registrations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("normalized_value"),
    )
    op.create_index(
        "ix_account_login_identifier_user_kind",
        "account_login_identifiers",
        ["user_id", "kind"],
    )
    op.create_index(
        "ix_account_login_identifier_pending",
        "account_login_identifiers",
        ["pending_registration_id"],
    )

    op.create_table(
        "account_purpose_challenges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject_kind", sa.String(32), nullable=False),
        sa.Column("pending_registration_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("issue_generation", sa.Integer(), nullable=False),
        sa.Column("binding_generation", sa.Integer(), nullable=False),
        sa.Column("key_version", sa.String(32), nullable=False),
        sa.Column("token_digest", sa.String(64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("failed_attempt_count", sa.Integer(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(
            ["pending_registration_id"],
            ["account_pending_registrations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "token_digest", name="uq_account_challenge_token_digest"
        ),
    )
    op.create_index(
        "ix_account_challenge_pending_purpose_current",
        "account_purpose_challenges",
        ["pending_registration_id", "purpose", "is_current"],
    )
    op.create_index(
        "ix_account_challenge_user_purpose_current",
        "account_purpose_challenges",
        ["user_id", "purpose", "is_current"],
    )
    op.create_index(
        "ix_account_challenge_subject_expiry",
        "account_purpose_challenges",
        ["subject_kind", "expires_at", "id"],
    )

    op.create_table(
        "account_lifecycle_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("transition", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("rate_category", sa.String(32), nullable=True),
        sa.Column("delivery_category", sa.String(32), nullable=True),
        sa.Column("duration_bucket", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_account_lifecycle_audit_account_created",
        "account_lifecycle_audit_events",
        ["account_id", "created_at"],
    )
    op.create_index(
        "ix_account_lifecycle_audit_actor_created",
        "account_lifecycle_audit_events",
        ["actor_id", "created_at"],
    )
    op.create_index(
        "ix_account_lifecycle_audit_purpose_outcome",
        "account_lifecycle_audit_events",
        ["purpose", "outcome", "created_at"],
    )
    _create_lifecycle_audit_immutability()

    op.create_table(
        "account_notification_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("challenge_id", sa.Uuid(), nullable=False),
        sa.Column("delivery_generation", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("locale", sa.String(8), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.String(255), nullable=False),
        sa.Column("dispatch_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terminal_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("safe_error_code", sa.String(96), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["challenge_id"], ["account_purpose_challenges.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", name="uq_account_notification_message_id"),
    )
    op.create_index(
        "ix_account_notification_status_created",
        "account_notification_deliveries",
        ["status", "created_at", "id"],
    )
    op.create_index(
        "ix_account_notification_challenge",
        "account_notification_deliveries",
        ["challenge_id", "created_at"],
    )

    with op.batch_alter_table("invitations") as batch:
        batch.alter_column(
            "invited_identity",
            existing_type=sa.String(128),
            type_=sa.String(320),
            existing_nullable=False,
        )
        batch.add_column(sa.Column("normalized_identity", sa.String(320), nullable=True))
        batch.add_column(sa.Column("identity_kind", sa.String(16), nullable=True))

    op.add_column(
        "jobs",
        sa.Column(
            "authority_kind",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'WORKSPACE'"),
        ),
    )
    with op.batch_alter_table("jobs") as batch:
        batch.alter_column(
            "workspace_id", existing_type=sa.Uuid(), nullable=True
        )
    for table in JOB_CHILD_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.alter_column(
                "workspace_id", existing_type=sa.Uuid(), nullable=True
            )
    op.create_index(
        "ix_jobs_authority_created",
        "jobs",
        ["authority_kind", "created_at", "id"],
    )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE "user"
            SET account_origin = CASE
                    WHEN admin_slot = 'primary' OR is_superuser = true
                        THEN 'GRANDFATHERED'
                    ELSE 'ADMIN_PROVISIONED'
                END,
                account_state = CASE
                    WHEN is_active = true THEN 'ACTIVE' ELSE 'DISABLED'
                END,
                email_state = 'UNSET',
                email_generation = 0,
                email_original = NULL,
                email_normalized = NULL,
                email_verified_at = NULL
            """
        )
    )
    _backfill_username_claims()
    _backfill_invitations()
    connection.execute(
        sa.text("UPDATE jobs SET authority_kind = 'WORKSPACE'")
    )


def _downgrade_blockers() -> dict[str, int]:
    connection = op.get_bind()
    statements = {
        "public_accounts": """
            SELECT COUNT(*) FROM "user"
            WHERE account_origin = 'PUBLIC'
               OR email_state <> 'UNSET'
               OR email_original IS NOT NULL
               OR email_normalized IS NOT NULL
               OR email_verified_at IS NOT NULL
        """,
        "pending_registrations": "SELECT COUNT(*) FROM account_pending_registrations",
        "lifecycle_challenges": "SELECT COUNT(*) FROM account_purpose_challenges",
        "notification_deliveries": "SELECT COUNT(*) FROM account_notification_deliveries",
        "lifecycle_audit": "SELECT COUNT(*) FROM account_lifecycle_audit_events",
        "nonlegacy_identifiers": """
            SELECT COUNT(*) FROM account_login_identifiers
            WHERE kind <> 'USERNAME' OR pending_registration_id IS NOT NULL
        """,
        "system_jobs": """
            SELECT COUNT(*) FROM jobs
            WHERE authority_kind = 'SYSTEM_ACCOUNT_LIFECYCLE'
        """,
        "email_invitations": """
            SELECT COUNT(*) FROM invitations WHERE identity_kind = 'EMAIL'
        """,
    }
    blockers: dict[str, int] = {}
    for category, statement in statements.items():
        count = int(connection.execute(sa.text(statement)).scalar_one())
        if count > 0:
            blockers[category] = count
    return blockers


def _drop_lifecycle_audit_immutability() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS account_lifecycle_audit_events_immutable "
            "ON account_lifecycle_audit_events"
        )
        op.execute("DROP FUNCTION IF EXISTS reject_account_lifecycle_audit_mutation")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS account_lifecycle_audit_events_no_update")
        op.execute("DROP TRIGGER IF EXISTS account_lifecycle_audit_events_no_delete")


def downgrade() -> None:
    blockers = _downgrade_blockers()
    if blockers:
        summary = ",".join(
            f"{category}={count}" for category, count in sorted(blockers.items())
        )
        raise RuntimeError(
            "Public account lifecycle downgrade refused; disable issuance and retain "
            f"the additive schema ({summary})"
        )

    op.drop_index("ix_jobs_authority_created", table_name="jobs")
    for table in reversed(JOB_CHILD_TABLES):
        with op.batch_alter_table(table) as batch:
            batch.alter_column(
                "workspace_id", existing_type=sa.Uuid(), nullable=False
            )
    with op.batch_alter_table("jobs") as batch:
        batch.alter_column(
            "workspace_id", existing_type=sa.Uuid(), nullable=False
        )
        batch.drop_column("authority_kind")

    with op.batch_alter_table("invitations") as batch:
        batch.drop_column("identity_kind")
        batch.drop_column("normalized_identity")
        batch.alter_column(
            "invited_identity",
            existing_type=sa.String(320),
            type_=sa.String(128),
            existing_nullable=False,
        )

    op.drop_index(
        "ix_account_notification_challenge",
        table_name="account_notification_deliveries",
    )
    op.drop_index(
        "ix_account_notification_status_created",
        table_name="account_notification_deliveries",
    )
    op.drop_table("account_notification_deliveries")

    _drop_lifecycle_audit_immutability()
    op.drop_index(
        "ix_account_lifecycle_audit_purpose_outcome",
        table_name="account_lifecycle_audit_events",
    )
    op.drop_index(
        "ix_account_lifecycle_audit_actor_created",
        table_name="account_lifecycle_audit_events",
    )
    op.drop_index(
        "ix_account_lifecycle_audit_account_created",
        table_name="account_lifecycle_audit_events",
    )
    op.drop_table("account_lifecycle_audit_events")

    op.drop_index(
        "ix_account_challenge_subject_expiry",
        table_name="account_purpose_challenges",
    )
    op.drop_index(
        "ix_account_challenge_user_purpose_current",
        table_name="account_purpose_challenges",
    )
    op.drop_index(
        "ix_account_challenge_pending_purpose_current",
        table_name="account_purpose_challenges",
    )
    op.drop_table("account_purpose_challenges")

    op.drop_index(
        "ix_account_login_identifier_pending",
        table_name="account_login_identifiers",
    )
    op.drop_index(
        "ix_account_login_identifier_user_kind",
        table_name="account_login_identifiers",
    )
    op.drop_table("account_login_identifiers")
    op.drop_index(
        "ix_account_pending_reclaim",
        table_name="account_pending_registrations",
    )
    op.drop_table("account_pending_registrations")

    op.drop_index("ix_user_email_normalized_shadow", table_name="user")
    with op.batch_alter_table("user") as batch:
        batch.drop_column("email_verified_at")
        batch.drop_column("email_generation")
        batch.drop_column("email_normalized")
        batch.drop_column("email_original")
        batch.drop_column("email_state")
        batch.drop_column("account_state")
        batch.drop_column("account_origin")
