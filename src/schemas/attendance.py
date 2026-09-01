"""Attendance check-in schemas."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class AttendanceCheckIn(BaseModel):
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    accuracy_meters: Decimal | None = Field(default=None, ge=0, le=10000)
    ticket_id: UUID | None = None


class PeerConfirmationInput(BaseModel):
    subject_id: UUID
    confirmed: bool


class QRAttendanceInput(BaseModel):
    attendance_id: UUID
    ticket_id: UUID


class OrganizerAttendanceInput(BaseModel):
    approve: bool
    reason: str = Field(min_length=2, max_length=500)


class AttendanceReviewInput(BaseModel):
    outcome: str = Field(pattern="^(cleared|confirmed|rejected)$")
    reason: str = Field(min_length=2, max_length=500)


class AttendanceReviewResponse(BaseModel):
    attendance_id: UUID
    event_id: UUID
    participant_id: UUID
    status: str
    review_status: str
    review_reason: str | None
    review_resolution: str | None
    suspicious_signal_count: int
