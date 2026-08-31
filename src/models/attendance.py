"""Attendance records and layered verification signals."""

import enum
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class AttendanceStatus(str, enum.Enum):
    NOT_CHECKED_IN = "not_checked_in"
    CHECKED_IN = "checked_in"
    GPS_VERIFIED = "gps_verified"
    QR_VERIFIED = "qr_verified"
    PEER_VERIFIED = "peer_verified"
    ORGANIZER_VERIFIED = "organizer_verified"
    REJECTED = "rejected"


class VerificationMethod(str, enum.Enum):
    GPS = "gps"
    QR = "qr"
    PEER = "peer"
    ORGANIZER = "organizer"


class PeerConfirmationDecision(str, enum.Enum):
    CONFIRMED = "confirmed"
    CANNOT_CONFIRM = "cannot_confirm"


class Attendance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attendances"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_attendance_event_user"),
        Index("ix_attendances_event_status", "event_id", "status"),
    )

    event_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ticket_id: Mapped[Any | None] = mapped_column(
        GUID(), ForeignKey("tickets.id", ondelete="SET NULL")
    )
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, native_enum=False, length=24),
        default=AttendanceStatus.NOT_CHECKED_IN,
        nullable=False,
    )
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    flagged_for_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    review_reason: Mapped[str | None] = mapped_column(Text)


class AttendanceVerification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attendance_verifications"
    __table_args__ = (
        UniqueConstraint("attendance_id", "method", name="uq_attendance_verification_method"),
        Index("ix_attendance_verifications_attendance_valid", "attendance_id", "is_valid"),
    )

    attendance_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("attendances.id", ondelete="CASCADE"), nullable=False
    )
    method: Mapped[VerificationMethod] = mapped_column(
        Enum(VerificationMethod, native_enum=False, length=16), nullable=False
    )
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verifier_id: Mapped[Any | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL")
    )
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    accuracy_meters: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    reason: Mapped[str | None] = mapped_column(String(500))


class PeerConfirmation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "peer_confirmations"
    __table_args__ = (
        UniqueConstraint(
            "event_id", "confirmer_id", "subject_id", name="uq_peer_confirmation_pair"
        ),
        Index("ix_peer_confirmations_subject_decision", "subject_id", "decision"),
    )

    event_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    confirmer_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    subject_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    decision: Mapped[PeerConfirmationDecision] = mapped_column(
        Enum(PeerConfirmationDecision, native_enum=False, length=20), nullable=False
    )
    suspicious: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
