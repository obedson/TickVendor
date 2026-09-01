"""Extensible administrator-defined achievement rules."""

from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class AchievementRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "achievement_rules"
    __table_args__ = (UniqueConstraint("community_id", "slug", name="uq_achievement_rule_slug"),)

    community_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("communities.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    condition_tree: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    reward_definition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="1", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AchievementAward(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "achievement_awards"
    __table_args__ = (UniqueConstraint("rule_id", "user_id", name="uq_achievement_award_rule_user"),)

    rule_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("achievement_rules.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    community_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("communities.id", ondelete="CASCADE"), nullable=False)
    awarded_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False)
