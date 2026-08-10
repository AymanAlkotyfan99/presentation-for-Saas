from datetime import datetime
import secrets
from typing import Any, Optional

import uuid

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String
from sqlmodel import Field, SQLModel

from enums.async_task_status import AsyncTaskStatus
from utils.datetime_utils import get_current_utc_datetime
from api.v1.auth.context import get_current_owner_id, get_current_workspace_id


class AsyncTaskModel(SQLModel, table=True):
    __tablename__ = "async_tasks"

    id: str = Field(
        default_factory=lambda: f"task-{secrets.token_hex(32)}",
        primary_key=True,
    )
    owner_id: Optional[uuid.UUID] = Field(
        default_factory=get_current_owner_id,
        exclude=True,
        sa_column=Column(
            ForeignKey("user.id", ondelete="CASCADE"), nullable=True, index=True
        ),
    )
    type: str = Field(index=True)
    status: AsyncTaskStatus = Field(
        sa_column=Column(String, index=True, nullable=False),
    )
    message: Optional[str] = None
    error: Optional[dict[str, Any]] = Field(sa_column=Column(JSON), default=None)
    data: Optional[dict[str, Any]] = Field(sa_column=Column(JSON), default=None)
    presentation_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(ForeignKey("presentations.id", ondelete="CASCADE"), nullable=True, index=True),
    )
    resource_id: Optional[str] = Field(
        default=None,
        sa_column=Column(String(128), nullable=True, index=True),
    )
    workspace_id: Optional[uuid.UUID] = Field(
        default_factory=get_current_workspace_id,
        sa_column=Column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True),
    )
    source_revision: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    actor_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    )
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=get_current_utc_datetime,
        )
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=get_current_utc_datetime,
            onupdate=get_current_utc_datetime,
        )
    )
