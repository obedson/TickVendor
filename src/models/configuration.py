"""Database-backed configurable business rules."""

from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class EventCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "event_categories"

    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PointRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "point_rules"
    __table_args__ = (
        UniqueConstraint("community_id", "source_type", name="uq_point_rule_community_source"),
    )

    community_id: Mapped[Any | None] = mapped_column(
        GUID(), ForeignKey("communities.id", ondelete="CASCADE")
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    max_awards_per_user: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ContributionBand(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "contribution_bands"
    __table_args__ = (
        UniqueConstraint("community_id", "currency", "minimum_amount", name="uq_contribution_band"),
    )

    community_id: Mapped[Any | None] = mapped_column(
        GUID(), ForeignKey("communities.id", ondelete="CASCADE")
    )
    currency: Mapped[str] = mapped_column(String(3), default="NGN", nullable=False)
    minimum_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    maximum_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    per_user_period_cap: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
