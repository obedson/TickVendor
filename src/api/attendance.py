"""Attendance API routes."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.authorization import EVENT_ATTENDANCE_STAFF_ROLES, require_event_staff_authority
from src.database import get_db
from src.models import (
    Attendance,
    AttendanceReviewStatus,
    AttendanceStatus,
    AttendanceVerification,
    AuditLog,
    Event,
    PeerConfirmation,
    Profile,
    Ticket,
    TicketStatus,
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


def event_or_404(db: Session, event_id: UUID, *, action: bool = True) -> Event:
    from src.services.availability import require_available
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if action:
        require_available(db, event)
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
    event_or_404(db, event_id)
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
    event_or_404(db, event_id)
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
    """Review and roster are event operations, so they follow event ownership, not community role."""
    require_event_staff_authority(db, event, user, staff_roles=EVENT_ATTENDANCE_STAFF_ROLES)


@router.get("/review", response_model=list[AttendanceReviewResponse])
def list_review(
    event_id: UUID, db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)], participant_id: UUID | None = None,
    reason: str | None = None, review_status: AttendanceReviewStatus = AttendanceReviewStatus.OPEN,
):
    event = event_or_404(db, event_id, action=False)
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
    event = event_or_404(db, event_id, action=False)
    _require_review_access(db, event, user)
    admission_statuses = [TicketStatus.PAID, TicketStatus.ACTIVE, TicketStatus.USED]
    participant_ids = select(Ticket.attendee_id).where(
        Ticket.event_id == event_id,
        Ticket.status.in_(admission_statuses),
    ).union(
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
        Ticket.event_id == event_id,
        Ticket.attendee_id.in_(user_ids),
        Ticket.status.in_(admission_statuses),
    ))) if user_ids else []
    attendances = list(db.scalars(select(Attendance).where(
        Attendance.event_id == event_id, Attendance.user_id.in_(user_ids)
    ))) if user_ids else []
    attendance_by_user = {item.user_id: item for item in attendances}
    ticket_statuses: dict[UUID, list[str]] = {}
    for ticket in tickets:
        ticket_statuses.setdefault(ticket.attendee_id, []).append(ticket.status.value)
    verification_methods: dict[UUID, list[str]] = {}
    locations: dict[UUID, list[dict]] = {}
    attendance_ids = [item.id for item in attendances]
    if attendance_ids:
        for signal in db.scalars(select(AttendanceVerification).where(
            AttendanceVerification.attendance_id.in_(attendance_ids),
        )):
            if signal.is_valid:
                verification_methods.setdefault(signal.attendance_id, []).append(signal.method.value)
            if signal.latitude is not None and signal.longitude is not None:
                # Legacy signals retain their original server-calculated distance in reason.
                distance = None
                if (signal.reason or "").startswith("distance_meters="):
                    try:
                        distance = float(signal.reason.split("=", 1)[1])
                    except ValueError:
                        pass
                locations.setdefault(signal.attendance_id, []).append({
                    "latitude": float(signal.latitude), "longitude": float(signal.longitude),
                    "accuracy_meters": float(signal.accuracy_meters) if signal.accuracy_meters is not None else None,
                    "distance_meters": distance, "operation": signal.method.value,
                    "radius_meters": event.geofence_radius_meters,
                    "max_accuracy_meters": event.geofence_max_accuracy_meters,
                    "outcome": "verified" if signal.is_valid else "unverified",
                    "recorded_at": signal.verified_at.isoformat(),
                })
    # Bound returned attempts to the latest per participant on this authorized event/page.
    ranked = select(
        AuditLog.id,
        func.row_number().over(partition_by=AuditLog.actor_id,
                               order_by=(AuditLog.occurred_at.desc(), AuditLog.id.desc())).label("rank"),
    ).where(AuditLog.target_type == "event", AuditLog.target_id == event_id,
            AuditLog.action == "attendance.location_submitted", AuditLog.actor_id.in_(user_ids)).subquery()
    attempts = {
        entry.actor_id: {**entry.metadata_json, "recorded_at": entry.occurred_at.isoformat()}
        for entry in db.scalars(select(AuditLog).join(ranked, ranked.c.id == AuditLog.id).where(ranked.c.rank == 1))
    } if user_ids else {}
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
            "location_evidence": locations.get(attendance.id, []) if attendance else [],
            "latest_location_attempt": attempts.get(participant.id),
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
    if target in {AttendanceReviewStatus.CONFIRMED, AttendanceReviewStatus.REJECTED}:
        organizer_verify(db, attendance, user, target == AttendanceReviewStatus.CONFIRMED, payload.reason)
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
