"""Configurable milestone definitions and requirements."""

from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class Milestone(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "milestones"
    __table_args__ = (UniqueConstraint("community_id", "slug", name="uq_milestone_community_slug"),)

    community_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("communities.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    icon_url: Mapped[str | None] = mapped_column(String(2048))
    reward_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class MilestoneRequirement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "milestone_requirements"
    __table_args__ = (UniqueConstraint("milestone_id", "metric", name="uq_milestone_requirement_metric"),)

    milestone_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("milestones.id", ondelete="CASCADE"), nullable=False)
    metric: Mapped[str] = mapped_column(String(80), nullable=False)
    operator: Mapped[str] = mapped_column(String(16), nullable=False)
    threshold: Mapped[int] = mapped_column(Integer, nullable=False)
