"""Published organization participation opportunities and registrations."""

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.models.base import GUID, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class OpportunityStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class OpportunityRegistrationStatus(str, enum.Enum):
    REGISTERED = "registered"
    COMPLETED = "completed"
    VERIFIED = "verified"
    REJECTED = "rejected"


class ActivityOpportunity(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "activity_opportunities"
    __table_args__ = (
        Index("ix_activity_opportunities_discovery", "status", "starts_at"),
        Index("ix_activity_opportunities_community_status", "community_id", "status"),
    )

    community_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("communities.id", ondelete="CASCADE"), nullable=False)
    created_by_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    activity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    dimension: Mapped[str] = mapped_column(String(32), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    location: Mapped[str | None] = mapped_column(String(500))
    capacity: Mapped[int | None] = mapped_column(Integer)
    members_only: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[OpportunityStatus] = mapped_column(Enum(OpportunityStatus, native_enum=False, length=16), default=OpportunityStatus.DRAFT, nullable=False)


class OpportunityRegistration(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "opportunity_registrations"
    __table_args__ = (
        UniqueConstraint("opportunity_id", "participant_id", name="uq_opportunity_registration_participant"),
        Index("ix_opportunity_registrations_opportunity_status", "opportunity_id", "status"),
    )

    opportunity_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("activity_opportunities.id", ondelete="CASCADE"), nullable=False)
    participant_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[OpportunityRegistrationStatus] = mapped_column(Enum(OpportunityRegistrationStatus, native_enum=False, length=16), default=OpportunityRegistrationStatus.REGISTERED, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by_id: Mapped[Any | None] = mapped_column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
