from datetime import datetime
import secrets
from typing import Optional
import uuid

from sqlalchemy import JSON, Column, ForeignKey, String
from sqlmodel import Field, SQLModel
from api.v1.auth.context import get_current_owner_id, get_current_workspace_id


class AsyncPresentationGenerationTaskModel(SQLModel, table=True):

    __tablename__ = "async_presentation_generation_tasks"

    id: str = Field(
        default_factory=lambda: f"task-{secrets.token_hex(32)}", primary_key=True
    )
    owner_id: Optional[uuid.UUID] = Field(
        default_factory=get_current_owner_id,
        exclude=True,
        sa_column=Column(
            ForeignKey("user.id", ondelete="CASCADE"), nullable=True, index=True
        ),
    )
    workspace_id: Optional[uuid.UUID] = Field(
        default_factory=get_current_workspace_id,
        sa_column=Column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True),
    )
    actor_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True),
    )
    presentation_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(ForeignKey("presentations.id", ondelete="CASCADE"), nullable=True, index=True),
    )
    resource_id: Optional[str] = Field(default=None, sa_column=Column(String(128), nullable=True, index=True))
    status: str
    message: Optional[str] = None
    error: Optional[dict] = Field(sa_column=Column(JSON), default=None)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    data: Optional[dict] = Field(sa_column=Column(JSON), default=None)
