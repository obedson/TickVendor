"""Configurable rank definitions and qualification requirements."""

from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class Rank(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ranks"
    __table_args__ = (UniqueConstraint("community_id", "slug", name="uq_rank_community_slug"),)

    community_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("communities.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    icon_url: Mapped[str | None] = mapped_column(String(2048))
    minimum_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class RankRequirement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rank_requirements"
    __table_args__ = (UniqueConstraint("rank_id", "requirement_type", "reference_id", name="uq_rank_requirement"),)

    rank_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("ranks.id", ondelete="CASCADE"), nullable=False)
    requirement_type: Mapped[str] = mapped_column(String(40), nullable=False)
    reference_id: Mapped[Any | None] = mapped_column(GUID())
    threshold: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class RankProgression(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rank_progressions"
    __table_args__ = (UniqueConstraint("rank_id", "user_id", name="uq_rank_progression_rank_user"),)

    rank_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("ranks.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    community_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("communities.id", ondelete="CASCADE"), nullable=False)
    achieved_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False)
