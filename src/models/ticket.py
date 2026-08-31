"""Ticket inventory, issued ticket, and order models."""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.payment import Payment


class TicketVisibility(str, enum.Enum):
    PUBLIC = "public"
    HIDDEN = "hidden"
    INVITE_ONLY = "invite_only"


class TicketStatus(str, enum.Enum):
    RESERVED = "reserved"
    PENDING_PAYMENT = "pending_payment"
    PAID = "paid"
    ACTIVE = "active"
    USED = "used"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    EXPIRED = "expired"


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    EXPIRED = "expired"


class TicketType(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ticket_types"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_ticket_type_price_nonnegative"),
        CheckConstraint("quantity >= 0", name="ck_ticket_type_quantity_nonnegative"),
        CheckConstraint("max_per_user > 0", name="ck_ticket_type_max_per_user_positive"),
        Index("ix_ticket_types_event_sales", "event_id", "sales_start", "sales_end"),
    )

    event_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="NGN", nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    sales_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sales_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    visibility: Mapped[TicketVisibility] = mapped_column(
        Enum(TicketVisibility, native_enum=False, length=16),
        default=TicketVisibility.PUBLIC,
        nullable=False,
    )
    max_per_user: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class Order(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (Index("ix_orders_user_status", "user_id", "status"),)

    reference: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    user_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    event_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("events.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False, length=16),
        default=OrderStatus.PENDING,
        nullable=False,
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="NGN", nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tickets: Mapped[list[Ticket]] = relationship(back_populates="order")
    payments: Mapped[list[Payment]] = relationship(back_populates="order")


class Ticket(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tickets"
    __table_args__ = (
        Index("ix_tickets_event_status", "event_id", "status"),
        Index("ix_tickets_attendee_status", "attendee_id", "status"),
    )

    public_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    qr_token: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    event_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("events.id", ondelete="RESTRICT"), nullable=False
    )
    ticket_type_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("ticket_types.id", ondelete="RESTRICT"), nullable=False
    )
    attendee_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    order_id: Mapped[Any | None] = mapped_column(
        GUID(), ForeignKey("orders.id", ondelete="SET NULL")
    )
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus, native_enum=False, length=24),
        default=TicketStatus.RESERVED,
        nullable=False,
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validated_by_id: Mapped[Any | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL")
    )

    order: Mapped[Order | None] = relationship(back_populates="tickets")

