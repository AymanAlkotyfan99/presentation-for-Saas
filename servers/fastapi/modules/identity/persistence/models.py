"""SQL mappings for pre-account identity lifecycle state.

``PendingRegistration`` is deliberately separate from ``User``. It has no
credential, role, session, workspace, or membership fields and is never an
authentication principal.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    event,
    text,
)
from sqlalchemy.orm import Mapper
from sqlmodel import Field, SQLModel

from utils.datetime_utils import get_current_utc_datetime


class PendingRegistration(SQLModel, table=True):
    __tablename__ = "account_pending_registrations"
    __table_args__ = (
        CheckConstraint(
            "state IN ('PENDING', 'ACTIVATED', 'ABANDONED')",
            name="ck_account_pending_state",
        ),
        CheckConstraint(
            "preferred_locale IN ('en', 'ar')",
            name="ck_account_pending_locale",
        ),
        CheckConstraint(
            "claim_generation >= 1",
            name="ck_account_pending_claim_generation",
        ),
        CheckConstraint(
            "reclaim_after > created_at",
            name="ck_account_pending_reclaim_order",
        ),
        UniqueConstraint(
            "activated_user_id", name="uq_account_pending_activated_user"
        ),
        Index(
            "ix_account_pending_reclaim",
            "state",
            "reclaim_after",
            "id",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    state: str = Field(
        default="PENDING", sa_column=Column(String(24), nullable=False)
    )
    email_original: str | None = Field(
        default=None, sa_column=Column(String(320), nullable=True)
    )
    email_normalized: str | None = Field(
        default=None, sa_column=Column(String(320), nullable=True)
    )
    preferred_locale: str = Field(sa_column=Column(String(8), nullable=False))
    claim_generation: int = Field(
        default=1, sa_column=Column(Integer, nullable=False, default=1)
    )
    created_at: datetime = Field(
        default_factory=get_current_utc_datetime,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    reclaim_after: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    terminal_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    purge_after: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    activated_user_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            Uuid,
            ForeignKey("user.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )


class AccountLoginIdentifier(SQLModel, table=True):
    __tablename__ = "account_login_identifiers"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('USERNAME', 'EMAIL')",
            name="ck_account_login_identifier_kind",
        ),
        CheckConstraint(
            "(user_id IS NOT NULL AND pending_registration_id IS NULL) OR "
            "(user_id IS NULL AND pending_registration_id IS NOT NULL)",
            name="ck_account_login_identifier_owner",
        ),
        Index(
            "uq_account_login_identifier_user_kind",
            "user_id",
            "kind",
            unique=True,
            sqlite_where=text("user_id IS NOT NULL"),
            postgresql_where=text("user_id IS NOT NULL"),
        ),
        Index(
            "uq_account_login_identifier_pending",
            "pending_registration_id",
            unique=True,
            sqlite_where=text("pending_registration_id IS NOT NULL"),
            postgresql_where=text("pending_registration_id IS NOT NULL"),
        ),
    )

    normalized_value: str = Field(
        sa_column=Column(String(320), primary_key=True, nullable=False)
    )
    user_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            Uuid, ForeignKey("user.id", ondelete="CASCADE"), nullable=True
        ),
    )
    pending_registration_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            Uuid,
            ForeignKey(
                "account_pending_registrations.id", ondelete="CASCADE"
            ),
            nullable=True,
        ),
    )
    kind: str = Field(sa_column=Column(String(16), nullable=False))
    created_at: datetime = Field(
        default_factory=get_current_utc_datetime,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class AccountPurposeChallenge(SQLModel, table=True):
    __tablename__ = "account_purpose_challenges"
    __table_args__ = (
        CheckConstraint(
            "subject_kind IN ('PENDING_REGISTRATION', 'USER')",
            name="ck_account_challenge_subject_kind",
        ),
        CheckConstraint(
            "purpose IN ('EMAIL_VERIFICATION', 'PASSWORD_RESET')",
            name="ck_account_challenge_purpose",
        ),
        CheckConstraint(
            "(subject_kind = 'PENDING_REGISTRATION' AND "
            "pending_registration_id IS NOT NULL AND user_id IS NULL AND "
            "purpose = 'EMAIL_VERIFICATION') OR "
            "(subject_kind = 'USER' AND user_id IS NOT NULL AND "
            "pending_registration_id IS NULL AND purpose = 'PASSWORD_RESET')",
            name="ck_account_challenge_subject_owner",
        ),
        CheckConstraint(
            "issue_generation >= 1 AND binding_generation >= 0",
            name="ck_account_challenge_generations",
        ),
        CheckConstraint(
            "failed_attempt_count >= 0 AND failed_attempt_count <= 5",
            name="ck_account_challenge_failed_attempts",
        ),
        CheckConstraint(
            "length(token_digest) = 64",
            name="ck_account_challenge_token_digest",
        ),
        CheckConstraint(
            "expires_at > issued_at",
            name="ck_account_challenge_expiry",
        ),
        CheckConstraint(
            "consumed_at IS NULL OR revoked_at IS NULL",
            name="ck_account_challenge_terminal_exclusive",
        ),
        CheckConstraint(
            "(consumed_at IS NULL AND revoked_at IS NULL) OR is_current = false",
            name="ck_account_challenge_terminal_not_current",
        ),
        UniqueConstraint(
            "token_digest", name="uq_account_challenge_token_digest"
        ),
        Index(
            "uq_account_challenge_pending_generation",
            "pending_registration_id",
            "purpose",
            "issue_generation",
            unique=True,
        ),
        Index(
            "uq_account_challenge_user_generation",
            "user_id",
            "purpose",
            "issue_generation",
            unique=True,
        ),
        Index(
            "uq_account_challenge_current_pending",
            "pending_registration_id",
            "purpose",
            unique=True,
            sqlite_where=text(
                "is_current = true AND pending_registration_id IS NOT NULL"
            ),
            postgresql_where=text(
                "is_current = true AND pending_registration_id IS NOT NULL"
            ),
        ),
        Index(
            "uq_account_challenge_current_user",
            "user_id",
            "purpose",
            unique=True,
            sqlite_where=text("is_current = true AND user_id IS NOT NULL"),
            postgresql_where=text("is_current = true AND user_id IS NOT NULL"),
        ),
        Index(
            "ix_account_challenge_subject_expiry",
            "subject_kind",
            "expires_at",
            "id",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    subject_kind: str = Field(sa_column=Column(String(32), nullable=False))
    pending_registration_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            Uuid,
            ForeignKey(
                "account_pending_registrations.id", ondelete="CASCADE"
            ),
            nullable=True,
        ),
    )
    user_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            Uuid, ForeignKey("user.id", ondelete="CASCADE"), nullable=True
        ),
    )
    purpose: str = Field(sa_column=Column(String(32), nullable=False))
    issue_generation: int = Field(sa_column=Column(Integer, nullable=False))
    binding_generation: int = Field(sa_column=Column(Integer, nullable=False))
    key_version: str = Field(sa_column=Column(String(32), nullable=False))
    token_digest: str = Field(
        exclude=True, sa_column=Column(String(64), nullable=False)
    )
    issued_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    is_current: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, default=True),
    )
    failed_attempt_count: int = Field(
        default=0, sa_column=Column(Integer, nullable=False, default=0)
    )
    consumed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    revoked_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    revocation_reason: str | None = Field(
        default=None, sa_column=Column(String(64), nullable=True)
    )


class AccountLifecycleAuditEvent(SQLModel, table=True):
    __tablename__ = "account_lifecycle_audit_events"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('accepted', 'completed', 'rejected', 'retryable', 'terminal')",
            name="ck_account_lifecycle_audit_outcome",
        ),
        Index(
            "ix_account_lifecycle_audit_account_created",
            "account_id",
            "created_at",
        ),
        Index(
            "ix_account_lifecycle_audit_actor_created",
            "actor_id",
            "created_at",
        ),
        Index(
            "ix_account_lifecycle_audit_purpose_outcome",
            "purpose",
            "outcome",
            "created_at",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    account_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            Uuid, ForeignKey("user.id", ondelete="SET NULL"), nullable=True
        ),
    )
    actor_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            Uuid, ForeignKey("user.id", ondelete="SET NULL"), nullable=True
        ),
    )
    purpose: str = Field(sa_column=Column(String(32), nullable=False))
    transition: str = Field(sa_column=Column(String(64), nullable=False))
    outcome: str = Field(sa_column=Column(String(16), nullable=False))
    rate_category: str | None = Field(
        default=None, sa_column=Column(String(32), nullable=True)
    )
    delivery_category: str | None = Field(
        default=None, sa_column=Column(String(32), nullable=True)
    )
    duration_bucket: str | None = Field(
        default=None, sa_column=Column(String(32), nullable=True)
    )
    created_at: datetime = Field(
        default_factory=get_current_utc_datetime,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


@event.listens_for(AccountLifecycleAuditEvent, "before_update")
@event.listens_for(AccountLifecycleAuditEvent, "before_delete")
def _reject_lifecycle_audit_mutation(
    _mapper: Mapper, _connection, _target: AccountLifecycleAuditEvent
) -> None:
    raise ValueError("Account lifecycle audit events are append-only")
