"""Attendance API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.database import get_db
from src.models import Attendance, AttendanceStatus, Event, PeerConfirmation, Ticket, User
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


@router.get("/peer-candidates")
def peer_candidates(
    event_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    event = event_or_404(db, event_id)
    if not event.peer_confirmation_enabled:
        raise HTTPException(status_code=409, detail="Peer confirmation is disabled")
    eligibility = set(event.peer_eligibility_statuses) or {
        AttendanceStatus.CHECKED_IN.value, AttendanceStatus.GPS_VERIFIED.value,
        AttendanceStatus.QR_VERIFIED.value, AttendanceStatus.PEER_VERIFIED.value,
        AttendanceStatus.ORGANIZER_VERIFIED.value,
    }
    confirmer = db.scalar(select(Attendance).where(
        Attendance.event_id == event_id, Attendance.user_id == user.id,
    ))
    if confirmer is None or confirmer.status.value not in eligibility:
        raise HTTPException(status_code=403, detail="Peer confirmation is not permitted")
    submitted = select(PeerConfirmation.subject_id).where(
        PeerConfirmation.event_id == event_id, PeerConfirmation.confirmer_id == user.id,
    )
    candidates = db.scalars(select(Attendance).where(
        Attendance.event_id == event_id, Attendance.user_id != user.id,
        Attendance.status.in_(eligibility), ~Attendance.user_id.in_(submitted),
    ).order_by(Attendance.user_id).limit(event.peer_selection_limit))
    return [{"participant_id": str(item.user_id)} for item in candidates]


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
