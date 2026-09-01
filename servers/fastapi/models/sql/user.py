import datetime
import uuid
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Uuid, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlmodel import SQLModel

from utils.datetime_utils import get_current_utc_datetime


class UserBase(DeclarativeBase):
    metadata = SQLModel.metadata


class User(UserBase):
    """Canonical account model used by the FastAPI Users manager."""

    __tablename__ = "user"
    __table_args__ = (
        CheckConstraint(
            "preferred_locale IS NULL OR preferred_locale IN ('en', 'ar')",
            name="ck_user_preferred_locale",
        ),
        CheckConstraint(
            "account_origin IS NULL OR account_origin IN "
            "('PUBLIC', 'ADMIN_PROVISIONED', 'GRANDFATHERED')",
            name="ck_user_account_origin",
        ),
        CheckConstraint(
            "account_state IS NULL OR account_state IN ('ACTIVE', 'DISABLED')",
            name="ck_user_account_state",
        ),
        CheckConstraint(
            "email_state IS NULL OR email_state IN ('UNSET', 'VERIFIED')",
            name="ck_user_email_state",
        ),
        CheckConstraint(
            "email_generation IS NULL OR email_generation >= 0",
            name="ck_user_email_generation",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    # The expand migration intentionally leaves the deployed column NOT NULL.
    # Optional typing lets compatibility code safely handle the public-account
    # shape before the later enforcement revision makes the column nullable.
    username: Mapped[Optional[str]] = mapped_column(
        String(128), unique=True, index=True, nullable=True
    )
    admin_slot: Mapped[Optional[str]] = mapped_column(
        String(32), unique=True, nullable=True
    )
    hashed_password: Mapped[str] = mapped_column(String(1024), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=get_current_utc_datetime
    )
    auth_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    preferred_locale: Mapped[Optional[str]] = mapped_column(
        String(8), nullable=True, default=None
    )
    account_origin: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, default="ADMIN_PROVISIONED"
    )
    account_state: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True, default="ACTIVE"
    )
    email_state: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True, default="UNSET"
    )
    email_original: Mapped[Optional[str]] = mapped_column(
        String(320), nullable=True, default=None
    )
    email_normalized: Mapped[Optional[str]] = mapped_column(
        String(320), nullable=True, default=None, index=True
    )
    email_generation: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=0
    )
    email_verified_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
