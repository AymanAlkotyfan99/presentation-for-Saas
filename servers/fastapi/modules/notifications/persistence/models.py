"""Safe delivery evidence for account lifecycle notifications."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid
from sqlmodel import Field, SQLModel

from utils.datetime_utils import get_current_utc_datetime


class NotificationDelivery(SQLModel, table=True):
    __tablename__ = "account_notification_deliveries"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('EMAIL_VERIFICATION', 'PASSWORD_RESET')",
            name="ck_account_notification_purpose",
        ),
        CheckConstraint(
            "locale IN ('en', 'ar')",
            name="ck_account_notification_locale",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'DISPATCHING', 'DELIVERED', 'RETRYABLE', "
            "'FAILED_TERMINAL', 'UNKNOWN_TERMINAL', 'SUPPRESSED')",
            name="ck_account_notification_status",
        ),
        CheckConstraint(
            "delivery_generation >= 1",
            name="ck_account_notification_generation",
        ),
        CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= 3",
            name="ck_account_notification_attempts",
        ),
        UniqueConstraint(
            "challenge_id",
            "delivery_generation",
            name="uq_account_notification_generation",
        ),
        UniqueConstraint("message_id", name="uq_account_notification_message_id"),
        Index(
            "ix_account_notification_status_created", "status", "created_at", "id"
        ),
        Index(
            "ix_account_notification_challenge", "challenge_id", "created_at"
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    challenge_id: UUID = Field(
        sa_column=Column(
            Uuid,
            ForeignKey("account_purpose_challenges.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    delivery_generation: int = Field(sa_column=Column(Integer, nullable=False))
    purpose: str = Field(sa_column=Column(String(32), nullable=False))
    locale: str = Field(sa_column=Column(String(8), nullable=False))
    status: str = Field(
        default="PENDING", sa_column=Column(String(24), nullable=False)
    )
    attempt_count: int = Field(
        default=0, sa_column=Column(Integer, nullable=False, default=0)
    )
    message_id: str = Field(sa_column=Column(String(255), nullable=False))
    dispatch_started_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    delivered_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    terminal_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    safe_error_code: str | None = Field(
        default=None, sa_column=Column(String(96), nullable=True)
    )
    created_at: datetime = Field(
        default_factory=get_current_utc_datetime,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=get_current_utc_datetime,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            onupdate=get_current_utc_datetime,
        ),
    )
