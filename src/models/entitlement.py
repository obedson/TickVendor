"""Ticket perks (entitlements) and their per-ticket redemption lifecycle.

An :class:`Entitlement` is organizer configuration attached to a ticket type. A
:class:`TicketEntitlement` is the per-issued-ticket state for one entitlement, and an
:class:`EntitlementRedemption` is one short-lived, single-use redemption credential.
Only hashes of the code and QR token are persisted, so a credential is never recoverable
from the database.
"""

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
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


class RedemptionMode(str, enum.Enum):
    """Which credential a staff member may accept for this entitlement."""

    QR = "qr"
    CODE = "code"
    EITHER = "either"


class TicketEntitlementStatus(str, enum.Enum):
    AVAILABLE = "available"
    REDEEMED = "redeemed"
    EXPIRED = "expired"
    REVOKED = "revoked"


class RedemptionStatus(str, enum.Enum):
    ISSUED = "issued"
    REDEEMED = "redeemed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class Entitlement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A configurable perk included with a ticket type."""

    __tablename__ = "entitlements"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_entitlement_quantity_nonnegative"),
        CheckConstraint(
            "max_redemptions_per_ticket >= 1", name="ck_entitlement_max_redemptions_positive"
        ),
        CheckConstraint(
            "min_attendance_minutes IS NULL OR min_attendance_minutes >= 0",
            name="ck_entitlement_min_attendance_nonnegative",
        ),
        Index("ix_entitlements_type_active", "ticket_type_id", "is_active"),
        Index("ix_entitlements_event_active", "event_id", "is_active"),
    )

    event_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    ticket_type_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("ticket_types.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    redemption_mode: Mapped[RedemptionMode] = mapped_column(
        Enum(RedemptionMode, native_enum=False, length=12),
        default=RedemptionMode.EITHER,
        nullable=False,
        server_default="EITHER",
    )
    redemption_starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    redemption_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requires_check_in: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    requires_checkout: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    min_attendance_minutes: Mapped[int | None] = mapped_column(Integer)
    requires_geofence: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_staff_validation: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    one_time: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_redemptions_per_ticket: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False, server_default="1"
    )
    eligibility: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class TicketEntitlement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-issued-ticket state for one configured entitlement."""

    __tablename__ = "ticket_entitlements"
    __table_args__ = (
        UniqueConstraint("ticket_id", "entitlement_id", name="uq_ticket_entitlement"),
        CheckConstraint("quantity_total >= 0", name="ck_ticket_entitlement_total_nonnegative"),
        CheckConstraint(
            "quantity_redeemed >= 0", name="ck_ticket_entitlement_redeemed_nonnegative"
        ),
        Index("ix_ticket_entitlements_ticket_status", "ticket_id", "status"),
        Index("ix_ticket_entitlements_entitlement", "entitlement_id"),
    )

    ticket_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    entitlement_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("entitlements.id", ondelete="CASCADE"), nullable=False
    )
    quantity_total: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    quantity_redeemed: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default="0"
    )
    status: Mapped[TicketEntitlementStatus] = mapped_column(
        Enum(TicketEntitlementStatus, native_enum=False, length=12),
        default=TicketEntitlementStatus.AVAILABLE,
        nullable=False,
        server_default="AVAILABLE",
    )
    last_redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EntitlementRedemption(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A short-lived, single-use credential issued only once eligibility is proven."""

    __tablename__ = "entitlement_redemptions"
    __table_args__ = (
        Index("ix_entitlement_redemptions_code_status", "code_hash", "status"),
        Index("ix_entitlement_redemptions_event_status", "event_id", "status"),
        Index("ix_entitlement_redemptions_ticket_status", "ticket_id", "status"),
    )

    ticket_entitlement_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("ticket_entitlements.id", ondelete="CASCADE"), nullable=False
    )
    event_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    ticket_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    entitlement_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("entitlements.id", ondelete="CASCADE"), nullable=False
    )
    holder_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    qr_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[RedemptionStatus] = mapped_column(
        Enum(RedemptionStatus, native_enum=False, length=12),
        default=RedemptionStatus.ISSUED,
        nullable=False,
        server_default="ISSUED",
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    redeemed_by_id: Mapped[Any | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL")
    )
    redeemed_method: Mapped[str | None] = mapped_column(String(12))
