"""Additive persistence metadata for the canonical Presentation Document."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Column, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from api.v1.auth.context import get_current_owner_id, get_current_workspace_id
from utils.datetime_utils import get_current_utc_datetime


class CanonicalConversionStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    PENDING = "PENDING"
    CONVERTING = "CONVERTING"
    CONVERTED = "CONVERTED"
    FAILED = "FAILED"
    UNSUPPORTED = "UNSUPPORTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


DOCUMENT_JSON = JSON(none_as_null=True).with_variant(
    JSONB(none_as_null=True), "postgresql"
)


class PresentationDocumentModel(SQLModel, table=True):
    __tablename__ = "presentation_documents"
    __table_args__ = (
        UniqueConstraint("presentation_id", name="uq_presentation_documents_presentation_id"),
        CheckConstraint("revision >= 1", name="ck_presentation_documents_revision"),
        CheckConstraint(
            "conversion_attempts >= 0 AND conversion_attempts <= 3",
            name="ck_presentation_documents_attempts",
        ),
        CheckConstraint(
            "schema_version = '1.0.0'",
            name="ck_presentation_documents_schema_version",
        ),
        CheckConstraint(
            "(document IS NULL AND checksum IS NULL) OR "
            "(document IS NOT NULL AND checksum IS NOT NULL AND length(checksum) = 64)",
            name="ck_presentation_documents_payload_checksum",
        ),
        Index("ix_presentation_documents_conversion_status", "conversion_status"),
        Index("ix_presentation_documents_owner_status", "owner_id", "conversion_status"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    presentation_id: UUID = Field(sa_column=Column(ForeignKey("presentations.id", ondelete="CASCADE"), nullable=False))
    owner_id: Optional[UUID] = Field(
        default_factory=get_current_owner_id,
        exclude=True,
        sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), nullable=True, index=True),
    )
    workspace_id: Optional[UUID] = Field(
        default_factory=get_current_workspace_id,
        sa_column=Column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True),
    )
    schema_version: str = Field(sa_column=Column(String(16), nullable=False))
    document: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(DOCUMENT_JSON, nullable=True))
    checksum: Optional[str] = Field(default=None, sa_column=Column(String(64), nullable=True, index=True))
    revision: int = Field(default=1, sa_column=Column(Integer, nullable=False, default=1))
    conversion_status: CanonicalConversionStatus = Field(
        default=CanonicalConversionStatus.NOT_STARTED,
        sa_column=Column(
            SAEnum(
                CanonicalConversionStatus,
                values_callable=lambda enum: [item.value for item in enum],
                name="canonical_conversion_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
    )
    conversion_error_code: Optional[str] = Field(default=None, sa_column=Column(String(128), nullable=True))
    conversion_error_details: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON, nullable=True))
    legacy_source_version: Optional[str] = Field(default=None, sa_column=Column(String(64), nullable=True))
    conversion_attempts: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))
    # Private compatibility lookup; never serialized in the document or API.
    asset_mappings: Optional[dict[str, str]] = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, default=get_current_utc_datetime))
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_current_utc_datetime, onupdate=get_current_utc_datetime)
    )
    converted_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
