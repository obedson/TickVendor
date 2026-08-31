"""Community activity and contribution records."""

import enum
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class EngagementDimension(str, enum.Enum):
    PARTICIPATION = "participation"
    EXECUTION = "execution"
    CONTRIBUTION = "contribution"
    SERVICE = "service"
    LEADERSHIP = "leadership"


class ActivityStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class ContributionType(str, enum.Enum):
    MONETARY = "monetary"
    EQUIPMENT = "equipment"
    MATERIALS = "materials"
    VOLUNTEER_TIME = "volunteer_time"
    SERVICES = "services"
    RESOURCES = "resources"


class Activity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "activities"
    __table_args__ = (Index("ix_activities_community_dimension", "community_id", "dimension"),)

    community_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("communities.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    event_id: Mapped[Any | None] = mapped_column(
        GUID(), ForeignKey("events.id", ondelete="SET NULL")
    )
    activity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    dimension: Mapped[EngagementDimension] = mapped_column(
        Enum(EngagementDimension, native_enum=False, length=16), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ActivityStatus] = mapped_column(
        Enum(ActivityStatus, native_enum=False, length=16),
        default=ActivityStatus.PENDING,
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verified_by_id: Mapped[Any | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL")
    )


class Contribution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "contributions"
    __table_args__ = (Index("ix_contributions_community_status", "community_id", "status"),)

    community_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("communities.id", ondelete="CASCADE"), nullable=False
    )
    contributor_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    contribution_type: Mapped[ContributionType] = mapped_column(
        Enum(ContributionType, native_enum=False, length=20), nullable=False
    )
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(128), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[ActivityStatus] = mapped_column(
        Enum(ActivityStatus, native_enum=False, length=16),
        default=ActivityStatus.PENDING,
        nullable=False,
    )
    verified_by_id: Mapped[Any | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL")
    )
