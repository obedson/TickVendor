"""Attendance API routes."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.authorization import require_community_role
from src.database import get_db
from src.models import (
    Attendance,
    AttendanceReviewStatus,
    AttendanceStatus,
    AttendanceVerification,
    Event,
    EventStaff,
    EventStaffRole,
    MembershipRole,
    PeerConfirmation,
    Profile,
    Ticket,
    User,
)
from src.schemas.attendance import (
    AttendanceCheckIn,
    AttendanceReviewInput,
    AttendanceReviewResponse,
    OrganizerAttendanceInput,
    PeerConfirmationInput,
    QRAttendanceInput,
)
from src.services.attendance import check_in, confirm_peer, organizer_verify, qr_verify
from src.services.notification import audit

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


def _review_payload(attendance: Attendance) -> dict:
    return {"attendance_id": attendance.id, "event_id": attendance.event_id,
            "participant_id": attendance.user_id, "status": attendance.status.value,
            "review_status": attendance.review_status.value, "review_reason": attendance.review_reason,
            "review_resolution": attendance.review_resolution,
            "suspicious_signal_count": len([part for part in (attendance.review_reason or "").split(";") if part])}


def _require_review_access(db: Session, event: Event, user: User) -> None:
    membership = require_community_role(db, event.community_id, user, MembershipRole.ORGANIZER)
    if user.role.value == "super_admin" or event.organizer_id == user.id or membership.role.value == "admin":
        return
    staff = db.scalar(select(EventStaff).where(
        EventStaff.event_id == event.id, EventStaff.user_id == user.id,
        EventStaff.role == EventStaffRole.ATTENDANCE_VERIFIER, EventStaff.is_active.is_(True)))
    if staff is None:
        raise HTTPException(status_code=403, detail="Attendance review permission required")


@router.get("/review", response_model=list[AttendanceReviewResponse])
def list_review(
    event_id: UUID, db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)], participant_id: UUID | None = None,
    reason: str | None = None, review_status: AttendanceReviewStatus = AttendanceReviewStatus.OPEN,
):
    event = event_or_404(db, event_id)
    _require_review_access(db, event, user)
    query = select(Attendance).where(
        Attendance.event_id == event_id, Attendance.flagged_for_review.is_(True),
        Attendance.review_status == review_status,
    )
    if participant_id:
        query = query.where(Attendance.user_id == participant_id)
    if reason:
        query = query.where(Attendance.review_reason.like(f"%{reason}%"))
    return [_review_payload(item) for item in db.scalars(query.order_by(Attendance.created_at.desc()))]


@router.get("/roster")
def attendance_roster(
    event_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Return ticket holders and attendance-only participants for organizer operations."""
    event = event_or_404(db, event_id)
    _require_review_access(db, event, user)
    participant_ids = select(Ticket.attendee_id).where(Ticket.event_id == event_id).union(
        select(Attendance.user_id).where(Attendance.event_id == event_id)
    )
    participants = db.execute(
        select(User, Profile)
        .join(Profile, Profile.user_id == User.id)
        .where(User.id.in_(participant_ids))
        .order_by(Profile.display_name, User.id)
        .limit(limit)
        .offset(offset)
    ).all()
    user_ids = [participant.id for participant, _profile in participants]
    tickets = list(db.scalars(select(Ticket).where(
        Ticket.event_id == event_id, Ticket.attendee_id.in_(user_ids)
    ))) if user_ids else []
    attendances = list(db.scalars(select(Attendance).where(
        Attendance.event_id == event_id, Attendance.user_id.in_(user_ids)
    ))) if user_ids else []
    attendance_by_user = {item.user_id: item for item in attendances}
    ticket_statuses: dict[UUID, list[str]] = {}
    for ticket in tickets:
        ticket_statuses.setdefault(ticket.attendee_id, []).append(ticket.status.value)
    verification_methods: dict[UUID, list[str]] = {}
    attendance_ids = [item.id for item in attendances]
    if attendance_ids:
        for signal in db.scalars(select(AttendanceVerification).where(
            AttendanceVerification.attendance_id.in_(attendance_ids),
            AttendanceVerification.is_valid.is_(True),
        )):
            verification_methods.setdefault(signal.attendance_id, []).append(signal.method.value)
    return [
        {
            "participant_id": str(participant.id),
            "display_name": profile.display_name,
            "email": participant.email,
            "ticket_statuses": sorted(ticket_statuses.get(participant.id, [])),
            "attendance_id": str(attendance.id) if attendance else None,
            "attendance_status": attendance.status.value if attendance else AttendanceStatus.NOT_CHECKED_IN.value,
            "checked_in_at": attendance.checked_in_at.isoformat() if attendance and attendance.checked_in_at else None,
            "verification_methods": sorted(verification_methods.get(attendance.id, [])) if attendance else [],
            "flagged_for_review": attendance.flagged_for_review if attendance else False,
        }
        for participant, profile in participants
        for attendance in [attendance_by_user.get(participant.id)]
    ]


@router.post("/{attendance_id}/review", response_model=AttendanceReviewResponse)
def resolve_review(
    event_id: UUID, attendance_id: UUID, payload: AttendanceReviewInput,
    db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)],
):
    event = event_or_404(db, event_id)
    _require_review_access(db, event, user)
    attendance = db.get(Attendance, attendance_id)
    if attendance is None or attendance.event_id != event_id:
        raise HTTPException(status_code=404, detail="Attendance not found")
    target = AttendanceReviewStatus(payload.outcome)
    if attendance.review_status != target or attendance.review_resolution != payload.reason:
        attendance.review_status = target
        attendance.reviewed_by_id = user.id
        attendance.reviewed_at = datetime.now(UTC)
        attendance.review_resolution = payload.reason
        db.commit()
        audit(db, actor_id=user.id, community_id=event.community_id,
              action="attendance.review.resolved", target_type="attendance", target_id=attendance.id,
              metadata={"outcome": target.value, "reason": payload.reason})
    return _review_payload(attendance)
