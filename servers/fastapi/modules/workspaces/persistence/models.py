"""SQL persistence models for workspace tenancy and security domains."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, event
from sqlalchemy.orm import Mapper
from sqlmodel import Field, SQLModel

from modules.workspaces.domain.models import MembershipStatus, Role
from utils.datetime_utils import get_current_utc_datetime


def _enum(enum, name):
    return SAEnum(enum, values_callable=lambda values: [item.value for item in values], name=name, native_enum=False, create_constraint=True)


class WorkspaceModel(SQLModel, table=True):
    __tablename__ = "workspaces"
    __table_args__ = (
        UniqueConstraint("personal_owner_id", name="uq_workspaces_personal_owner"),
        CheckConstraint("length(name) >= 1 AND length(name) <= 160", name="ck_workspaces_name"),
        Index("ix_workspaces_created_by", "created_by"),
    )
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(sa_column=Column(String(160), nullable=False))
    is_personal: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False))
    personal_owner_id: UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), nullable=True))
    created_by: UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, default=get_current_utc_datetime))
    updated_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, default=get_current_utc_datetime, onupdate=get_current_utc_datetime))


class MembershipModel(SQLModel, table=True):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_memberships_workspace_user"),
        Index("ix_memberships_user_status", "user_id", "status"),
        Index("ix_memberships_workspace_role", "workspace_id", "role"),
    )
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    workspace_id: UUID = Field(sa_column=Column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False))
    user_id: UUID = Field(sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False))
    role: Role = Field(sa_column=Column(_enum(Role, "workspace_role"), nullable=False))
    status: MembershipStatus = Field(default=MembershipStatus.ACTIVE, sa_column=Column(_enum(MembershipStatus, "membership_status"), nullable=False))
    permission_overrides: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False, default=list))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, default=get_current_utc_datetime))
    updated_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, default=get_current_utc_datetime, onupdate=get_current_utc_datetime))


class InvitationModel(SQLModel, table=True):
    __tablename__ = "invitations"
    __table_args__ = (
        UniqueConstraint("token_digest", name="uq_invitations_token_digest"),
        CheckConstraint("length(token_digest) = 64", name="ck_invitations_token_digest"),
        CheckConstraint(
            "identity_kind IS NULL OR identity_kind IN ('USERNAME', 'EMAIL')",
            name="ck_invitations_identity_kind",
        ),
        Index("ix_invitations_workspace_state", "workspace_id", "accepted_at", "revoked_at", "expires_at"),
        Index("ix_invitations_identity", "workspace_id", "invited_identity"),
    )
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    workspace_id: UUID = Field(sa_column=Column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False))
    invited_identity: str = Field(sa_column=Column(String(320), nullable=False))
    normalized_identity: str | None = Field(
        default=None, sa_column=Column(String(320), nullable=True)
    )
    identity_kind: str | None = Field(
        default=None, sa_column=Column(String(16), nullable=True)
    )
    role: Role = Field(sa_column=Column(_enum(Role, "invitation_role"), nullable=False))
    token_digest: str = Field(exclude=True, sa_column=Column(String(64), nullable=False))
    created_by: UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, default=get_current_utc_datetime))
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    accepted_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    accepted_by: UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True))
    revoked_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    send_count: int = Field(default=1, sa_column=Column(Integer, nullable=False, default=1))


class ServiceAccountModel(SQLModel, table=True):
    __tablename__ = "service_accounts"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_service_accounts_workspace_name"),)
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    workspace_id: UUID = Field(sa_column=Column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True))
    name: str = Field(sa_column=Column(String(128), nullable=False))
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    created_by: UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, default=get_current_utc_datetime))
    updated_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, default=get_current_utc_datetime, onupdate=get_current_utc_datetime))


class ApiCredentialModel(SQLModel, table=True):
    __tablename__ = "api_credentials"
    __table_args__ = (
        UniqueConstraint("key_prefix", name="uq_api_credentials_key_prefix"),
        CheckConstraint("length(secret_digest) = 64", name="ck_api_credentials_secret_digest"),
        Index("ix_api_credentials_workspace_active", "workspace_id", "revoked_at", "expires_at"),
    )
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    workspace_id: UUID = Field(sa_column=Column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False))
    service_account_id: UUID = Field(sa_column=Column(ForeignKey("service_accounts.id", ondelete="CASCADE"), nullable=False, index=True))
    key_prefix: str = Field(sa_column=Column(String(64), nullable=False))
    secret_digest: str = Field(exclude=True, sa_column=Column(String(64), nullable=False))
    created_by: UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, default=get_current_utc_datetime))
    expires_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    revoked_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    last_used_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class ApiCredentialScopeModel(SQLModel, table=True):
    __tablename__ = "api_credential_scopes"
    __table_args__ = (UniqueConstraint("credential_id", "scope", name="uq_api_credential_scopes_value"),)
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    credential_id: UUID = Field(sa_column=Column(ForeignKey("api_credentials.id", ondelete="CASCADE"), nullable=False, index=True))
    scope: str = Field(sa_column=Column(String(64), nullable=False))


class AuditEventModel(SQLModel, table=True):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_workspace_created", "workspace_id", "created_at"),)
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    workspace_id: UUID = Field(sa_column=Column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False))
    actor_id: UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True))
    actor_service_account_id: UUID | None = Field(default=None, sa_column=Column(ForeignKey("service_accounts.id", ondelete="SET NULL"), nullable=True))
    event_type: str = Field(sa_column=Column(String(64), nullable=False))
    subject_type: str = Field(sa_column=Column(String(64), nullable=False))
    subject_id: str = Field(sa_column=Column(String(128), nullable=False))
    safe_metadata: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, default=dict))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, default=get_current_utc_datetime))


def _immutable(_mapper: Mapper, _connection, target: object) -> None:
    raise ValueError(f"{type(target).__name__} rows are append-only")


event.listen(AuditEventModel, "before_update", _immutable)
event.listen(AuditEventModel, "before_delete", _immutable)
