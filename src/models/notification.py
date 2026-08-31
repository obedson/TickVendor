"""Notifications, audit records, and configurable leaderboards."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_read", "user_id", "read_at"),)

    user_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    deduplication_key: Mapped[str | None] = mapped_column(String(200), unique=True, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_target", "target_type", "target_id"),)

    actor_id: Mapped[Any | None] = mapped_column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
    community_id: Mapped[Any | None] = mapped_column(GUID(), ForeignKey("communities.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[Any | None] = mapped_column(GUID())
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class Leaderboard(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "leaderboards"
    __table_args__ = (UniqueConstraint("community_id", "slug", name="uq_leaderboard_community_slug"),)

    community_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("communities.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    metric: Mapped[str] = mapped_column(String(64), nullable=False)
    period: Mapped[str] = mapped_column(String(32), nullable=False)
    max_entries: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
