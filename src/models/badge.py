"""Badge definitions and idempotent awards."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class Badge(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "badges"
    __table_args__ = (UniqueConstraint("community_id", "slug", name="uq_badge_community_slug"),)

    community_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("communities.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    icon_url: Mapped[str | None] = mapped_column(String(2048))
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    requirements: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    reward_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class BadgeAward(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "badge_awards"
    __table_args__ = (UniqueConstraint("badge_id", "user_id", name="uq_badge_award_user"),)

    badge_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("badges.id", ondelete="RESTRICT"), nullable=False)
    user_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event_id: Mapped[Any | None] = mapped_column(
        GUID(), ForeignKey("events.id", ondelete="SET NULL"), index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    awarded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    awarded_by_id: Mapped[Any | None] = mapped_column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(Text)
