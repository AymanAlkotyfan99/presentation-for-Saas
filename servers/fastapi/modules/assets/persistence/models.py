"""SQL persistence for stable private asset identities."""

from __future__ import annotations

from datetime import datetime
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
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel

from modules.assets.domain.models import AssetState, MalwareScanStatus, RetentionClass, UploadState
from utils.datetime_utils import get_current_utc_datetime


def _enum(enum, name: str):
    return SAEnum(
        enum,
        values_callable=lambda values: [item.value for item in values],
        name=name,
        native_enum=False,
        create_constraint=False,
    )


class AssetModel(SQLModel, table=True):
    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="ck_assets_size"),
        Index("ix_assets_workspace_created", "workspace_id", "created_at"),
        Index("ix_assets_workspace_state", "workspace_id", "state"),
        Index("ix_assets_checksum", "workspace_id", "checksum_sha256"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    workspace_id: UUID = Field(sa_column=Column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False))
    owner_id: UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True))
    creator_service_account_id: UUID | None = Field(default=None, sa_column=Column(ForeignKey("service_accounts.id", ondelete="SET NULL"), nullable=True))
    storage_provider: str = Field(sa_column=Column(String(64), nullable=False))
    storage_key: str = Field(exclude=True, sa_column=Column(String(512), nullable=False, unique=True))
    original_filename: str | None = Field(default=None, sa_column=Column(String(255), nullable=True))
    checksum_sha256: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    size_bytes: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))
    declared_mime: str | None = Field(default=None, sa_column=Column(String(128), nullable=True))
    detected_mime: str | None = Field(default=None, sa_column=Column(String(128), nullable=True))
    state: AssetState = Field(default=AssetState.UPLOADING, sa_column=Column(_enum(AssetState, "asset_state"), nullable=False))
    malware_scan_status: MalwareScanStatus = Field(default=MalwareScanStatus.PENDING, sa_column=Column(_enum(MalwareScanStatus, "asset_scan_status"), nullable=False))
    retention_class: RetentionClass = Field(default=RetentionClass.WORKSPACE, sa_column=Column(_enum(RetentionClass, "asset_retention_class"), nullable=False))
    current_version: int = Field(default=1, sa_column=Column(Integer, nullable=False, default=1))
    accessibility_metadata: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, default=dict))
    expires_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=get_current_utc_datetime, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=get_current_utc_datetime, sa_column=Column(DateTime(timezone=True), nullable=False, onupdate=get_current_utc_datetime))
    deleted_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class ObjectVersionModel(SQLModel, table=True):
    __tablename__ = "object_versions"
    __table_args__ = (
        UniqueConstraint("asset_id", "version_number", name="uq_object_versions_asset_version"),
        UniqueConstraint("storage_provider", "storage_key", name="uq_object_versions_storage_key"),
        Index("ix_object_versions_workspace_asset", "workspace_id", "asset_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    asset_id: UUID = Field(sa_column=Column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False))
    workspace_id: UUID = Field(sa_column=Column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False))
    version_number: int = Field(sa_column=Column(Integer, nullable=False))
    storage_provider: str = Field(sa_column=Column(String(64), nullable=False))
    storage_key: str = Field(exclude=True, sa_column=Column(String(512), nullable=False))
    checksum_sha256: str = Field(sa_column=Column(String(64), nullable=False))
    size_bytes: int = Field(sa_column=Column(Integer, nullable=False))
    detected_mime: str = Field(sa_column=Column(String(128), nullable=False))
    created_at: datetime = Field(default_factory=get_current_utc_datetime, sa_column=Column(DateTime(timezone=True), nullable=False))


class UploadSessionModel(SQLModel, table=True):
    __tablename__ = "upload_sessions"
    __table_args__ = (
        Index("ix_upload_sessions_workspace_state", "workspace_id", "state", "expires_at"),
        Index("ix_upload_sessions_asset", "asset_id", "created_at"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    asset_id: UUID = Field(sa_column=Column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False))
    workspace_id: UUID = Field(sa_column=Column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False))
    actor_id: UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True))
    actor_service_account_id: UUID | None = Field(default=None, sa_column=Column(ForeignKey("service_accounts.id", ondelete="SET NULL"), nullable=True))
    storage_provider: str = Field(sa_column=Column(String(64), nullable=False))
    storage_key: str = Field(exclude=True, sa_column=Column(String(512), nullable=False))
    target_version: int = Field(default=1, sa_column=Column(Integer, nullable=False, default=1))
    provider_upload_id: str | None = Field(default=None, exclude=True, sa_column=Column(String(512), nullable=True))
    state: UploadState = Field(default=UploadState.CREATED, sa_column=Column(_enum(UploadState, "upload_state"), nullable=False))
    expected_size: int = Field(sa_column=Column(Integer, nullable=False))
    expected_checksum_sha256: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    declared_mime: str = Field(sa_column=Column(String(128), nullable=False))
    multipart: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False))
    completed_parts: list[dict] = Field(default_factory=list, sa_column=Column(JSON, nullable=False, default=list))
    created_at: datetime = Field(default_factory=get_current_utc_datetime, sa_column=Column(DateTime(timezone=True), nullable=False))
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    aborted_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class AssetReferenceModel(SQLModel, table=True):
    __tablename__ = "asset_references"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "asset_id", "resource_type", "resource_id", "reference_type",
            name="uq_asset_reference_binding",
        ),
        Index("ix_asset_references_resource", "workspace_id", "resource_type", "resource_id"),
        Index("ix_asset_references_asset", "workspace_id", "asset_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    workspace_id: UUID = Field(sa_column=Column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False))
    asset_id: UUID = Field(sa_column=Column(ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False))
    resource_type: str = Field(sa_column=Column(String(64), nullable=False))
    resource_id: str = Field(sa_column=Column(String(128), nullable=False))
    reference_type: str = Field(sa_column=Column(String(64), nullable=False))
    created_by: UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True))
    created_at: datetime = Field(default_factory=get_current_utc_datetime, sa_column=Column(DateTime(timezone=True), nullable=False))
