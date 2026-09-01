"""Attendance API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.database import get_db
from src.models import Attendance, Event, Ticket, User
from src.schemas.attendance import (
    AttendanceCheckIn,
    OrganizerAttendanceInput,
    PeerConfirmationInput,
    QRAttendanceInput,
)
from src.services.attendance import check_in, confirm_peer, organizer_verify, qr_verify

router = APIRouter(prefix="/events/{event_id}/attendance", tags=["attendance"])


def event_or_404(db: Session, event_id: UUID) -> Event:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.post("/check-in")
def attendance_check_in(
    event_id: UUID, payload: AttendanceCheckIn,
    db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)],
):
    attendance = check_in(db, event_or_404(db, event_id), user, payload)
    return {"attendance_id": str(attendance.id), "status": attendance.status.value,
            "confidence_score": str(attendance.confidence_score)}


@router.post("/peer-confirmations", status_code=201)
def peer_confirmation(
    event_id: UUID, payload: PeerConfirmationInput,
    db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)],
):
    confirmation = confirm_peer(db, event_or_404(db, event_id), user, payload.subject_id, payload.confirmed)
    return {"confirmation_id": str(confirmation.id), "decision": confirmation.decision.value}


@router.post("/qr-verify")
def qr_attendance(
    event_id: UUID,
    payload: QRAttendanceInput,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    attendance = db.get(Attendance, payload.attendance_id)
    ticket = db.get(Ticket, payload.ticket_id)
    if attendance is None or attendance.event_id != event_id or ticket is None:
        raise HTTPException(status_code=404, detail="Attendance or ticket not found")
    updated = qr_verify(db, attendance, ticket, user)
    return {"status": updated.status.value, "confidence_score": str(updated.confidence_score)}


@router.post("/{attendance_id}/organizer-review")
def organizer_attendance_review(
    event_id: UUID,
    attendance_id: UUID,
    payload: OrganizerAttendanceInput,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    attendance = db.get(Attendance, attendance_id)
    if attendance is None or attendance.event_id != event_id:
        raise HTTPException(status_code=404, detail="Attendance not found")
    updated = organizer_verify(db, attendance, user, payload.approve, payload.reason)
    return {"status": updated.status.value, "confidence_score": str(updated.confidence_score)}
