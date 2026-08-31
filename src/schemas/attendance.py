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
