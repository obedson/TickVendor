"""Durable scheduled notification work items."""

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class ScheduledNotificationStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    RETRYABLE = "retryable"
    DELIVERED = "delivered"
    FAILED = "failed"


class ScheduledNotification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scheduled_notifications"
    __table_args__ = (
        Index("ix_scheduled_notifications_due", "status", "scheduled_at"),
        Index("ix_scheduled_notifications_tenant", "community_id", "status"),
    )

    user_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    community_id: Mapped[Any | None] = mapped_column(GUID(), ForeignKey("communities.id", ondelete="CASCADE"))
    notification_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[ScheduledNotificationStatus] = mapped_column(
        Enum(ScheduledNotificationStatus, native_enum=False, length=16),
        default=ScheduledNotificationStatus.PENDING, nullable=False,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
