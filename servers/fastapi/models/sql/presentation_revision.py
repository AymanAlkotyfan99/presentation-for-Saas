"""Immutable canonical presentation revision and command-patch records."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapper
from sqlmodel import Field, SQLModel

from api.v1.auth.context import get_current_owner_id, get_current_workspace_id
from utils.datetime_utils import get_current_utc_datetime


REVISION_JSON = JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")


class PresentationRevisionModel(SQLModel, table=True):
    __tablename__ = "presentation_revisions"
    __table_args__ = (
        UniqueConstraint("presentation_id", "revision", name="uq_presentation_revisions_number"),
        CheckConstraint("revision >= 1", name="ck_presentation_revisions_number"),
        CheckConstraint("parent_revision IS NULL OR parent_revision >= 1", name="ck_presentation_revisions_parent"),
        CheckConstraint("length(checksum) = 64", name="ck_presentation_revisions_checksum"),
        Index("ix_presentation_revisions_owner_presentation", "owner_id", "presentation_id"),
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
    revision: int = Field(sa_column=Column(Integer, nullable=False))
    parent_revision: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    checksum: str = Field(sa_column=Column(String(64), nullable=False))
    # Periodic anchors bound replay. Non-anchor revisions are reconstructed from
    # the closest preceding anchor and the immutable patch stream.
    snapshot_document: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(REVISION_JSON, nullable=True))
    source: str = Field(default="command", sa_column=Column(String(32), nullable=False))
    actor_id: Optional[UUID] = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True))
    restored_from_revision: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    retention_class: str = Field(default="standard", sa_column=Column(String(32), nullable=False))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, default=get_current_utc_datetime))


class PresentationRevisionPatchModel(SQLModel, table=True):
    __tablename__ = "presentation_revision_patches"
    __table_args__ = (
        UniqueConstraint("presentation_id", "revision", name="uq_presentation_revision_patches_number"),
        UniqueConstraint(
            "presentation_id", "actor_scope", "idempotency_key",
            name="uq_presentation_revision_patches_idempotency",
        ),
        CheckConstraint("revision >= 1 AND base_revision >= 0", name="ck_presentation_revision_patches_numbers"),
        CheckConstraint("command_count >= 0 AND command_count <= 500", name="ck_presentation_revision_patches_command_count"),
        CheckConstraint("length(request_checksum) = 64", name="ck_presentation_revision_patches_checksum"),
        Index("ix_presentation_revision_patches_owner_presentation", "owner_id", "presentation_id"),
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
    revision: int = Field(sa_column=Column(Integer, nullable=False))
    base_revision: int = Field(sa_column=Column(Integer, nullable=False))
    actor_scope: str = Field(sa_column=Column(String(128), nullable=False))
    idempotency_key: str = Field(sa_column=Column(String(128), nullable=False))
    request_checksum: str = Field(sa_column=Column(String(64), nullable=False))
    commands: list[dict[str, Any]] = Field(sa_column=Column(REVISION_JSON, nullable=False))
    command_count: int = Field(sa_column=Column(Integer, nullable=False))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, default=get_current_utc_datetime))


def _immutable(_mapper: Mapper, _connection, target: object) -> None:
    raise ValueError(f"{type(target).__name__} rows are immutable")


event.listen(PresentationRevisionModel, "before_update", _immutable)
event.listen(PresentationRevisionModel, "before_delete", _immutable)
event.listen(PresentationRevisionPatchModel, "before_update", _immutable)
event.listen(PresentationRevisionPatchModel, "before_delete", _immutable)
