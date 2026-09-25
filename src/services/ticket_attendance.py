"""Participant self check-in and self checkout for geofenced event tickets.

Location is verified exactly twice - once at admission and once at departure - and both
timestamps come from the server. There is no background or continuous location tracking.
"""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models import (
    Attendance,
    AttendanceStatus,
    AttendanceVerification,
    Event,
    EventStatus,
    Ticket,
    TicketAssignmentState,
    TicketStatus,
    TicketType,
    User,
    VerificationMethod,
)
from src.schemas.attendance import AttendanceCheckIn
from src.services.attendance import (
    award_qualified_attendance,
    calculate_attendance_confidence,
)
from src.services.attendance_location import location_evidence, location_guidance, record_location
from src.services.availability import require_available
from src.services.event import as_utc
from src.services.notification import audit, notify

_BLOCKED_TICKET_STATUSES = {
    TicketStatus.CANCELLED,
    TicketStatus.REFUNDED,
    TicketStatus.EXPIRED,
    TicketStatus.RESERVED,
    TicketStatus.PENDING_PAYMENT,
}

def _load_ticket(db: Session, event_id: UUID, ticket_id: UUID, user: User) -> Ticket:
    ticket = db.scalar(select(Ticket).where(Ticket.id == ticket_id).with_for_update())
    # Unknown ticket and somebody else's ticket are indistinguishable to the caller.
    if ticket is None or ticket.event_id != event_id or ticket.attendee_id != user.id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


def require_event_staff(db: Session, event: Event, user: User, *, staff_roles=None) -> None:
    """Authorized organizer, admin, platform admin, or active event staff member.

    Delegates to the shared event-operational helper so ticket validation and benefit redemption
    apply exactly the same owner-scoped rule as attendance verification: an Organizer of this
    community who does not run this event and holds no staff assignment on it is refused.

    ``staff_roles`` narrows which EventStaff roles qualify; callers pass one of the
    ``EVENT_*_STAFF_ROLES`` groups from :mod:`src.authorization` so that a job's authority is
    declared once rather than restated at each call site. Omit it only where the question is
    genuinely "is this person attached to this event at all?".
    """
    from src.authorization import require_event_staff_authority

    require_event_staff_authority(db, event, user, staff_roles=staff_roles)


def _geofence_point(db, user, event: Event, payload: AttendanceCheckIn | None, *, label: str) -> tuple | None:
    """Return validated coordinates, or None when the event has no geofence."""
    if not event.geofence_enabled:
        record_location(db, event, user, location_evidence(event, payload), operation=label)
        return None
    if event.geofence_radius_meters is None:
        raise HTTPException(
            status_code=409,
            detail="This event's geofence is not fully configured; ask the organizer to set a radius",
        )
    if payload is None or payload.latitude is None or payload.longitude is None:
        raise HTTPException(status_code=422, detail=f"Location is required for {label}")
    if event.venue is None or event.venue.latitude is None or event.venue.longitude is None:
        raise HTTPException(
            status_code=409, detail="This event has no venue coordinates; ask the organizer to set them"
        )
    evidence = location_evidence(event, payload)
    outside = evidence["outcome"] == "outside_geofence"
    # Persist an outside attempt before returning 422; no admission or reward is created.
    record_location(db, event, user, evidence, operation=label, commit=outside)
    if outside:
        raise HTTPException(status_code=422, detail=location_guidance(evidence))
    distance = evidence["distance_meters"]
    return payload.latitude, payload.longitude, payload.accuracy_meters, distance, evidence["outcome"]


def redemption_limit_reached(db: Session, ticket: Ticket, holder_id) -> bool:
    """One attendee may redeem at most `max_per_user` admissions for a ticket type."""
    ticket_type = db.get(TicketType, ticket.ticket_type_id)
    if ticket_type is None:
        return False
    already = db.scalar(select(func.count()).select_from(Ticket).where(
        Ticket.event_id == ticket.event_id,
        Ticket.ticket_type_id == ticket.ticket_type_id,
        Ticket.attendee_id == holder_id,
        Ticket.id != ticket.id,
        Ticket.status == TicketStatus.USED,
    )) or 0
    return already >= ticket_type.max_per_user


def enforce_redemption_limit(db: Session, ticket: Ticket, holder_id) -> None:
    if redemption_limit_reached(db, ticket, holder_id):
        raise HTTPException(
            status_code=409,
            detail="One attendee may only redeem one admission of this ticket type; transfer or share the other tickets",
        )


def _attendance_for(db: Session, event_id: UUID, user_id) -> Attendance | None:
    return db.scalar(select(Attendance).where(
        Attendance.event_id == event_id, Attendance.user_id == user_id
    ).with_for_update())


def self_check_in(
    db: Session, event_id: UUID, ticket_id: UUID, user: User, payload: AttendanceCheckIn | None
) -> dict:
    ticket = _load_ticket(db, event_id, ticket_id, user)
    event = require_available(db, db.get(Event, event_id))
    if event.status != EventStatus.PUBLISHED:
        raise HTTPException(status_code=409, detail="This event is not open for check-in")
    if not event.self_check_in_enabled:
        raise HTTPException(status_code=409, detail="Self check-in is not enabled for this event")
    if ticket.status in _BLOCKED_TICKET_STATUSES:
        raise HTTPException(status_code=409, detail="This ticket is no longer valid")
    if ticket.assignment_state != TicketAssignmentState.CLAIMED:
        raise HTTPException(
            status_code=409, detail="Claim or transfer this ticket to an attendee before check-in"
        )
    now = datetime.now(UTC)
    if event.check_in_opens_at and now < as_utc(event.check_in_opens_at):
        raise HTTPException(status_code=409, detail="Check-in is not open yet")
    if event.check_in_closes_at and now > as_utc(event.check_in_closes_at):
        raise HTTPException(status_code=409, detail="Check-in has closed")

    attendance = _attendance_for(db, event_id, user.id)
    if attendance is not None and attendance.checked_in_at is not None:
        # Idempotent: a repeated check-in returns the recorded state and never duplicates
        # verification signals or Impact.
        if attendance.ticket_id not in (None, ticket.id):
            raise HTTPException(status_code=409, detail="You have already checked in to this event")
        return check_in_state(db, attendance)

    enforce_redemption_limit(db, ticket, user.id)
    point = _geofence_point(db, user, event, payload, label="self check-in")

    if attendance is None:
        attendance = Attendance(
            event_id=event_id, user_id=user.id, ticket_id=ticket.id,
            status=AttendanceStatus.CHECKED_IN, checked_in_at=now,
        )
        db.add(attendance)
        db.flush()
    else:
        attendance.ticket_id = ticket.id
        attendance.checked_in_at = now
        if attendance.status in {AttendanceStatus.NOT_CHECKED_IN, AttendanceStatus.REJECTED}:
            attendance.status = AttendanceStatus.CHECKED_IN
    if point is not None:
        latitude, longitude, accuracy, distance, outcome = point
        pending_review = outcome != "verified"
        db.add(AttendanceVerification(
            attendance_id=attendance.id, method=VerificationMethod.GPS, is_valid=not pending_review,
            verified_at=now, verifier_id=user.id, latitude=latitude, longitude=longitude,
            accuracy_meters=accuracy, reason=f"distance_meters={distance:.2f}",
        ))
        if pending_review:
            attendance.flagged_for_review = True
            attendance.review_reason = location_guidance(location_evidence(event, payload))
        else:
            attendance.status = AttendanceStatus.GPS_VERIFIED
    db.flush()
    if not attendance.flagged_for_review:
        ticket.status = TicketStatus.USED
        ticket.used_at = now
        ticket.validated_by_id = user.id
    db.commit()
    if point is not None:
        calculate_attendance_confidence(db, attendance)
    audit(db, actor_id=user.id, community_id=event.community_id, action="attendance.checked_in",
          target_type="attendance", target_id=attendance.id,
          metadata={"event_id": str(event_id), "ticket_id": str(ticket.id), "method": "self",
                    "gps_submitted": point is not None})
    award_qualified_attendance(db, attendance)
    notify(db, user.id, "check_in_pending" if attendance.flagged_for_review else "check_in_confirmed",
           "Check-in awaiting review" if attendance.flagged_for_review else "Check-in successful",
           (f"Your location for {event.title} was sent to the organizer for verification."
            if attendance.flagged_for_review else f"You are checked in to {event.title}."),
           {"event_id": str(event_id), "ticket_id": str(ticket.id)},
           community_id=event.community_id, deduplication_key=f"checkin:{attendance.id}", commit=False)
    db.commit()
    return check_in_state(db, attendance)


def self_check_out(
    db: Session, event_id: UUID, ticket_id: UUID, user: User, payload: AttendanceCheckIn | None
) -> dict:
    ticket = _load_ticket(db, event_id, ticket_id, user)
    event = require_available(db, db.get(Event, event_id))
    # The same lifecycle gate as self check-in: an unpublished, cancelled or completed event is
    # not accepting check-out either.
    if event.status != EventStatus.PUBLISHED:
        raise HTTPException(status_code=409, detail="This event is not open for checkout")
    if not event.self_checkout_enabled:
        raise HTTPException(status_code=409, detail="Self checkout is not enabled for this event")
    if ticket.status in _BLOCKED_TICKET_STATUSES:
        raise HTTPException(status_code=409, detail="This ticket is no longer valid")
    attendance = _attendance_for(db, event_id, user.id)
    if attendance is None or attendance.checked_in_at is None:
        raise HTTPException(status_code=409, detail="You must check in before checking out")
    if attendance.checked_out_at is not None:
        return check_in_state(db, attendance)
    now = datetime.now(UTC)
    if event.checkout_opens_at and now < as_utc(event.checkout_opens_at):
        raise HTTPException(status_code=409, detail="Checkout is not open yet")
    point = _geofence_point(db, user, event, payload, label="checkout")
    if point is not None:
        latitude, longitude, accuracy, distance, outcome = point
        if outcome != "verified":
            raise HTTPException(status_code=422, detail=location_guidance(location_evidence(event, payload)))
        db.add(AttendanceVerification(
            attendance_id=attendance.id, method=VerificationMethod.GPS_CHECKOUT, is_valid=True,
            verified_at=now, verifier_id=user.id, latitude=latitude, longitude=longitude,
            accuracy_meters=accuracy, reason=f"distance_meters={distance:.2f}",
        ))
    checked_in = as_utc(attendance.checked_in_at)
    attendance.checked_out_at = now
    attendance.duration_seconds = max(0, int((now - checked_in).total_seconds()))
    db.commit()
    audit(db, actor_id=user.id, community_id=event.community_id, action="attendance.checked_out",
          target_type="attendance", target_id=attendance.id,
          metadata={"event_id": str(event_id), "ticket_id": str(ticket.id),
                    "duration_seconds": attendance.duration_seconds,
                    "gps_submitted": point is not None})
    notify(db, user.id, "check_out_confirmed", "Checkout recorded",
           f"Your attendance at {event.title} was finalized.",
           {"event_id": str(event_id), "ticket_id": str(ticket.id)},
           community_id=event.community_id, deduplication_key=f"checkout:{attendance.id}", commit=False)
    db.commit()
    return check_in_state(db, attendance)


def check_in_state(db: Session, attendance: Attendance) -> dict:
    methods = [row for row in db.scalars(select(AttendanceVerification.method).where(
        AttendanceVerification.attendance_id == attendance.id,
        AttendanceVerification.is_valid.is_(True),
    ))]
    return {
        "attendance_id": str(attendance.id),
        "event_id": str(attendance.event_id),
        "ticket_id": str(attendance.ticket_id) if attendance.ticket_id else None,
        "status": attendance.status.value,
        "checked_in_at": attendance.checked_in_at,
        "checked_out_at": attendance.checked_out_at,
        "duration_seconds": attendance.duration_seconds,
        "viable_methods": sorted({m.value if hasattr(m, "value") else str(m) for m in methods}),
        "pending_review": attendance.flagged_for_review,
    }
