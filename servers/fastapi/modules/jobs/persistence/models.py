"""SQL persistence models for durable jobs and messaging evidence."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlmodel import Field, SQLModel

from modules.jobs.domain.models import (
    JobAuthorityKind,
    JobStatus,
    QueueClass,
    RetryClass,
)
from utils.datetime_utils import get_current_utc_datetime


def _enum(enum, name: str):
    return SAEnum(
        enum,
        values_callable=lambda values: [item.value for item in values],
        name=name,
        native_enum=False,
        create_constraint=False,
    )


class JobModel(SQLModel, table=True):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "idempotency_scope", "idempotency_key",
            name="uq_jobs_workspace_idempotency",
        ),
        Index(
            "uq_jobs_system_idempotency",
            "authority_kind",
            "idempotency_scope",
            "idempotency_key",
            unique=True,
            sqlite_where=text(
                "workspace_id IS NULL AND "
                "authority_kind = 'SYSTEM_ACCOUNT_LIFECYCLE'"
            ),
            postgresql_where=text(
                "workspace_id IS NULL AND "
                "authority_kind = 'SYSTEM_ACCOUNT_LIFECYCLE'"
            ),
        ),
        CheckConstraint(
            "(authority_kind = 'WORKSPACE' AND workspace_id IS NOT NULL) OR "
            "(authority_kind = 'SYSTEM_ACCOUNT_LIFECYCLE' AND "
            "workspace_id IS NULL AND owner_id IS NULL AND actor_id IS NULL AND "
            "actor_service_account_id IS NULL AND operation IN "
            "('account.notification.deliver.v1', 'account.pending.reconcile.v1'))",
            name="ck_jobs_authority_scope",
        ),
        CheckConstraint("progress >= 0 AND progress <= 100", name="ck_jobs_progress"),
        CheckConstraint("attempt_count >= 0 AND max_attempts >= 1", name="ck_jobs_attempts"),
        Index("ix_jobs_queue_available", "queue_class", "status", "available_at"),
        Index("ix_jobs_workspace_created", "workspace_id", "created_at"),
        Index("ix_jobs_lease", "status", "lease_until"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    workspace_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True)
    )
    authority_kind: JobAuthorityKind = Field(
        default=JobAuthorityKind.WORKSPACE,
        sa_column=Column(
            _enum(JobAuthorityKind, "job_authority_kind"),
            nullable=False,
            default=JobAuthorityKind.WORKSPACE,
        ),
    )
    owner_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    )
    actor_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    )
    actor_service_account_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("service_accounts.id", ondelete="SET NULL"), nullable=True),
    )
    operation: str = Field(sa_column=Column(String(96), nullable=False))
    queue_class: QueueClass = Field(sa_column=Column(_enum(QueueClass, "job_queue_class"), nullable=False))
    status: JobStatus = Field(
        default=JobStatus.PENDING, sa_column=Column(_enum(JobStatus, "job_status"), nullable=False)
    )
    progress: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))
    progress_message: str | None = Field(default=None, sa_column=Column(String(256), nullable=True))
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    result: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    payload_schema_version: int = Field(default=1, sa_column=Column(Integer, nullable=False))
    result_schema_version: int = Field(default=1, sa_column=Column(Integer, nullable=False))
    request_hash: str = Field(sa_column=Column(String(64), nullable=False))
    idempotency_scope: str = Field(sa_column=Column(String(192), nullable=False))
    idempotency_key: str = Field(sa_column=Column(String(128), nullable=False))
    resource_type: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    resource_id: str | None = Field(default=None, sa_column=Column(String(128), nullable=True))
    source_revision: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    attempt_count: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))
    max_attempts: int = Field(default=3, sa_column=Column(Integer, nullable=False, default=3))
    available_at: datetime = Field(
        default_factory=get_current_utc_datetime,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    lease_owner: str | None = Field(default=None, sa_column=Column(String(128), nullable=True))
    lease_token: UUID | None = Field(default=None, sa_column=Column(Uuid(), nullable=True))
    lease_until: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    heartbeat_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    cancellation_requested_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    trace_id: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    parent_trace_id: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    safe_error_code: str | None = Field(default=None, sa_column=Column(String(96), nullable=True))
    safe_error_message: str | None = Field(default=None, sa_column=Column(String(512), nullable=True))
    created_at: datetime = Field(
        default_factory=get_current_utc_datetime,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    finished_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    updated_at: datetime = Field(
        default_factory=get_current_utc_datetime,
        sa_column=Column(DateTime(timezone=True), nullable=False, onupdate=get_current_utc_datetime),
    )


class JobAttemptModel(SQLModel, table=True):
    __tablename__ = "job_attempts"
    __table_args__ = (
        UniqueConstraint("job_id", "attempt_number", name="uq_job_attempt_number"),
        Index("ix_job_attempts_workspace_job", "workspace_id", "job_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    job_id: UUID = Field(sa_column=Column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False))
    workspace_id: UUID | None = Field(default=None, sa_column=Column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True))
    attempt_number: int = Field(sa_column=Column(Integer, nullable=False))
    worker_id: str = Field(sa_column=Column(String(128), nullable=False))
    lease_token: UUID = Field(default_factory=uuid4, sa_column=Column(Uuid(), nullable=False))
    claimed_at: datetime = Field(default_factory=get_current_utc_datetime, sa_column=Column(DateTime(timezone=True), nullable=False))
    started_at: datetime = Field(default_factory=get_current_utc_datetime, sa_column=Column(DateTime(timezone=True), nullable=False))
    heartbeat_at: datetime = Field(default_factory=get_current_utc_datetime, sa_column=Column(DateTime(timezone=True), nullable=False))
    lease_until: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    finished_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    retry_class: RetryClass | None = Field(default=None, sa_column=Column(_enum(RetryClass, "job_attempt_retry_class"), nullable=True))
    safe_error_code: str | None = Field(default=None, sa_column=Column(String(96), nullable=True))
    safe_error_message: str | None = Field(default=None, sa_column=Column(String(512), nullable=True))


class OutboxMessageModel(SQLModel, table=True):
    __tablename__ = "outbox_messages"
    __table_args__ = (
        UniqueConstraint("message_id", name="uq_outbox_message_id"),
        Index("ix_outbox_pending", "published_at", "available_at", "created_at"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    message_id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID | None = Field(default=None, sa_column=Column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True))
    job_id: UUID = Field(sa_column=Column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False))
    topic: str = Field(sa_column=Column(String(96), nullable=False))
    queue_class: QueueClass = Field(sa_column=Column(_enum(QueueClass, "outbox_queue_class"), nullable=False))
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    available_at: datetime = Field(default_factory=get_current_utc_datetime, sa_column=Column(DateTime(timezone=True), nullable=False))
    publish_attempts: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))
    last_error_code: str | None = Field(default=None, sa_column=Column(String(96), nullable=True))
    created_at: datetime = Field(default_factory=get_current_utc_datetime, sa_column=Column(DateTime(timezone=True), nullable=False))
    published_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class ConsumerInboxModel(SQLModel, table=True):
    __tablename__ = "consumer_inbox"
    __table_args__ = (
        UniqueConstraint("consumer_id", "message_id", name="uq_consumer_inbox_delivery"),
        Index("ix_consumer_inbox_workspace_received", "workspace_id", "received_at"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    workspace_id: UUID | None = Field(default=None, sa_column=Column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True))
    job_id: UUID = Field(sa_column=Column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False))
    consumer_id: str = Field(sa_column=Column(String(128), nullable=False))
    message_id: UUID
    received_at: datetime = Field(default_factory=get_current_utc_datetime, sa_column=Column(DateTime(timezone=True), nullable=False))
    processed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class DeadLetterModel(SQLModel, table=True):
    __tablename__ = "dead_letters"
    __table_args__ = (Index("ix_dead_letters_workspace_created", "workspace_id", "created_at"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    workspace_id: UUID | None = Field(default=None, sa_column=Column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True))
    job_id: UUID = Field(sa_column=Column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False))
    operation: str = Field(sa_column=Column(String(96), nullable=False))
    attempt_number: int = Field(sa_column=Column(Integer, nullable=False))
    safe_error_code: str = Field(sa_column=Column(String(96), nullable=False))
    safe_error_message: str | None = Field(default=None, sa_column=Column(String(512), nullable=True))
    retry_class: RetryClass = Field(sa_column=Column(_enum(RetryClass, "dead_letter_retry_class"), nullable=False))
    created_at: datetime = Field(default_factory=get_current_utc_datetime, sa_column=Column(DateTime(timezone=True), nullable=False))


class JobEventModel(SQLModel, table=True):
    __tablename__ = "job_events"
    __table_args__ = (Index("ix_job_events_workspace_job_id", "workspace_id", "job_id", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    workspace_id: UUID | None = Field(default=None, sa_column=Column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True))
    job_id: UUID = Field(sa_column=Column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False))
    event_type: str = Field(sa_column=Column(String(64), nullable=False))
    safe_data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=get_current_utc_datetime, sa_column=Column(DateTime(timezone=True), nullable=False))
