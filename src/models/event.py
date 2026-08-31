"""Event, venue, and event-staff models."""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.models.base import GUID, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class EventStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class LocationType(str, enum.Enum):
    PHYSICAL = "physical"
    ONLINE = "online"
    HYBRID = "hybrid"


class EventStaffRole(str, enum.Enum):
    MANAGER = "manager"
    CHECK_IN = "check_in"
    TICKET_VALIDATOR = "ticket_validator"
    ATTENDANCE_VERIFIER = "attendance_verifier"


class Venue(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "venues"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str | None] = mapped_column(String(120), index=True)
    region: Mapped[str | None] = mapped_column(String(120))
    country_code: Mapped[str] = mapped_column(String(2), default="NG", nullable=False)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))


class Event(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_discovery", "status", "starts_at"),
        Index("ix_events_community_status", "community_id", "status"),
        Index("ix_events_search_title", "status", "title"),
    )

    community_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("communities.id", ondelete="CASCADE"), nullable=False
    )
    organizer_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    venue_id: Mapped[Any | None] = mapped_column(
        GUID(), ForeignKey("venues.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False, unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(320))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Africa/Lagos", nullable=False)
    location_type: Mapped[LocationType] = mapped_column(
        Enum(LocationType, native_enum=False, length=16), nullable=False
    )
    online_url: Mapped[str | None] = mapped_column(String(2048))
    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus, native_enum=False, length=16),
        default=EventStatus.DRAFT,
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    geofence_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    geofence_radius_meters: Mapped[int | None] = mapped_column(Integer)
    check_in_opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    check_in_closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    peer_confirmation_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confirmations_required: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    organizer_verification_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    qr_attendance_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    venue: Mapped[Venue | None] = relationship()
    staff: Mapped[list[EventStaff]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class EventStaff(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "event_staff"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_staff_event_user"),
        Index("ix_event_staff_user_active", "user_id", "is_active"),
    )

    event_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[EventStaffRole] = mapped_column(
        Enum(EventStaffRole, native_enum=False, length=24), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    event: Mapped[Event] = relationship(back_populates="staff")
