"""Notification preference model."""

from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class NotificationPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (UniqueConstraint("user_id", name="uq_notification_preference_user"),)

    user_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    push_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    muted_types: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
