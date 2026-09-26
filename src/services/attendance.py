"""Attendance check-in, geofence, and layered verification services."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.authorization import (
    EVENT_ADMISSION_STAFF_ROLES,
    EVENT_ATTENDANCE_STAFF_ROLES,
    require_event_staff_authority,
)
from src.models import (
    Attendance,
    AttendanceStatus,
    AttendanceVerification,
    Event,
    ImpactTransaction,
    ImpactTransactionStatus,
    PeerConfirmation,
    PeerConfirmationDecision,
    PointRule,
    Ticket,
    TicketStatus,
    User,
    VerificationMethod,
)
from src.monitoring import emit
from src.schemas.attendance import AttendanceCheckIn
from src.services.attendance_location import location_evidence, location_guidance, record_location
from src.services.event import as_utc
from src.services.impact import award_points
from src.services.notification import audit, notify
from src.services.recognition import evaluate_recognition


def haversine_meters(lat1: Decimal, lon1: Decimal, lat2: Decimal, lon2: Decimal) -> float:
    phi1, phi2 = radians(float(lat1)), radians(float(lat2))
    dphi = radians(float(lat2 - lat1)); dlambda = radians(float(lon2 - lon1))
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 6_371_000 * 2 * asin(sqrt(a))


def calculate_attendance_confidence(db: Session, attendance: Attendance) -> Attendance:
    event = db.get(Event, attendance.event_id)
    signals = list(db.scalars(select(AttendanceVerification).where(
        AttendanceVerification.attendance_id == attendance.id
    )))
    organizer = next((signal for signal in signals if signal.method == VerificationMethod.ORGANIZER), None)
    if organizer and not organizer.is_valid:
        attendance.status = AttendanceStatus.REJECTED
        attendance.confidence_score = Decimal(0)
        db.commit()
        return attendance
    valid = {signal.method for signal in signals if signal.is_valid}
    required = {VerificationMethod(method) for method in event.required_verification_methods}
    weights = {VerificationMethod.GPS: Decimal(40), VerificationMethod.QR: Decimal(50),
               VerificationMethod.PEER: Decimal(30), VerificationMethod.ORGANIZER: Decimal(100)}
    attendance.confidence_score = min(Decimal(100), sum((weights[item] for item in valid), Decimal(0)))
    precedence = ((VerificationMethod.ORGANIZER, AttendanceStatus.ORGANIZER_VERIFIED),
                  (VerificationMethod.QR, AttendanceStatus.QR_VERIFIED),
                  (VerificationMethod.GPS, AttendanceStatus.GPS_VERIFIED),
                  (VerificationMethod.PEER, AttendanceStatus.PEER_VERIFIED))
    attendance.status = next((status for method, status in precedence if method in valid), AttendanceStatus.CHECKED_IN)
    # An explicit organizer approval is the configured human fallback for uncertain device GPS.
    if VerificationMethod.ORGANIZER in valid:
        attendance.status = AttendanceStatus.ORGANIZER_VERIFIED
    elif required and not required.issubset(valid):
        attendance.status = AttendanceStatus.CHECKED_IN
    elif not required and valid:
        attendance.status = next((status for method, status in precedence if method in valid), AttendanceStatus.CHECKED_IN)
    db.commit()
    return attendance


def award_qualified_attendance(db: Session, attendance: Attendance) -> None:
    event = db.get(Event, attendance.event_id)
    valid = {signal.method for signal in db.scalars(select(AttendanceVerification).where(
        AttendanceVerification.attendance_id == attendance.id,
        AttendanceVerification.is_valid.is_(True),
    ))}
    required = {VerificationMethod(method) for method in event.required_verification_methods}
    organizer_override = VerificationMethod.ORGANIZER in valid
    if attendance.status == AttendanceStatus.REJECTED or (not organizer_override and not required.issubset(valid)):
        return
    if db.scalar(select(PointRule.id).where(
        PointRule.source_type == "attendance", PointRule.is_active.is_(True),
        (PointRule.community_id == event.community_id) | PointRule.community_id.is_(None),
    )) is not None:
        award_points(db, user_id=attendance.user_id, community_id=event.community_id,
                     source_type="attendance", source_id=attendance.id,
                     idempotency_key=f"attendance:{attendance.id}:verified",
                     reason=f"Attendance verified: {event.title}", event_id=event.id)
    evaluate_recognition(db, attendance.user_id, event.community_id)


def _compensate_attendance_points(
    db: Session, attendance: Attendance, *, approve: bool, decision_key: str
) -> None:
    """Net attendance points without deleting or rewriting historical transactions."""
    posted = list(db.scalars(select(ImpactTransaction).where(
        ImpactTransaction.source_type == "attendance",
        ImpactTransaction.source_id == attendance.id,
        ImpactTransaction.status == ImpactTransactionStatus.POSTED,
    )))
    net = sum(item.points for item in posted)
    if approve:
        if net <= 0:
            original = next((item for item in posted if item.points > 0), None)
            if original is not None:
                db.add(ImpactTransaction(
                    idempotency_key=f"attendance:{attendance.id}:decision:{decision_key}:restore",
                    user_id=attendance.user_id,
                    community_id=original.community_id,
                    points=original.points,
                    source_type="attendance",
                    source_id=attendance.id,
                    event_id=attendance.event_id,
                    reason="Attendance points restored after organizer reconsideration",
                    status=ImpactTransactionStatus.POSTED,
                    reversed_transaction_id=original.id,
                ))
        return
    if net > 0:
        original = next((item for item in posted if item.points > 0), None)
        db.add(ImpactTransaction(
            idempotency_key=f"attendance:{attendance.id}:decision:{decision_key}:reversal",
            user_id=attendance.user_id,
            community_id=original.community_id,
            points=-net,
            source_type="attendance",
            source_id=attendance.id,
            event_id=attendance.event_id,
            reason="Attendance points reversed after organizer rejection",
            status=ImpactTransactionStatus.POSTED,
            reversed_transaction_id=original.id,
        ))


def record_qr_attendance(
    db: Session,
    event: Event,
    ticket: Ticket,
    verifier: User,
    *,
    verified_at: datetime | None = None,
) -> tuple[Attendance, bool]:
    """Attach one QR signal to the attendee's event record without committing.

    Ticket validation and the dedicated attendance endpoint both use this primitive so a
    successful entrance scan cannot leave the ticket and attendance records disconnected.
    """
    now = verified_at or datetime.now(UTC)
    attendance = db.scalar(select(Attendance).where(
        Attendance.event_id == event.id,
        Attendance.user_id == ticket.attendee_id,
    ).with_for_update())
    if attendance is None:
        attendance = Attendance(
            event_id=event.id,
            user_id=ticket.attendee_id,
            ticket_id=ticket.id,
            status=AttendanceStatus.CHECKED_IN,
            checked_in_at=now,
        )
        db.add(attendance)
        db.flush()
    elif attendance.ticket_id is None:
        attendance.ticket_id = ticket.id

    existing = db.scalar(select(AttendanceVerification).where(
        AttendanceVerification.attendance_id == attendance.id,
        AttendanceVerification.method == VerificationMethod.QR,
    ))
    if existing is not None:
        return attendance, False

    db.add(AttendanceVerification(
        attendance_id=attendance.id,
        method=VerificationMethod.QR,
        is_valid=True,
        verified_at=now,
        verifier_id=verifier.id,
    ))
    return attendance, True


def evaluate_attendance_abuse(db: Session, attendance: Attendance) -> Attendance:
    """Flag implausible transitions and burst patterns conservatively."""
    current = db.scalar(select(AttendanceVerification).where(
        AttendanceVerification.attendance_id == attendance.id,
        AttendanceVerification.method == VerificationMethod.GPS,
        AttendanceVerification.is_valid.is_(True),
    ))
    if current is None or current.latitude is None or current.longitude is None:
        return attendance
    previous = db.scalar(select(AttendanceVerification).join(
        Attendance, Attendance.id == AttendanceVerification.attendance_id,
    ).where(
        Attendance.user_id == attendance.user_id, Attendance.id != attendance.id,
        AttendanceVerification.method == VerificationMethod.GPS,
        AttendanceVerification.is_valid.is_(True),
        AttendanceVerification.verified_at < current.verified_at,
    ).order_by(AttendanceVerification.verified_at.desc()))
    speed_kmh = 0
    if previous is not None:
        elapsed = (as_utc(current.verified_at) - as_utc(previous.verified_at)).total_seconds()
        speed_kmh = haversine_meters(previous.latitude, previous.longitude,
                                     current.latitude, current.longitude) / elapsed * 3.6 if elapsed > 0 else 0
    if previous is not None and speed_kmh > 1_000 and "impossible_location_transition" not in (attendance.review_reason or ""):
        attendance.flagged_for_review = True
        attendance.review_reason = ((attendance.review_reason + "; ") if attendance.review_reason else "") + \
            f"impossible_location_transition:speed_kmh={speed_kmh:.1f}"
        emit("attendance_abuse_signal", reason="impossible_location_transition",
             attendance_id=str(attendance.id), event_id=str(attendance.event_id))
        db.commit()
    burst = db.scalar(select(func.count()).select_from(AttendanceVerification).join(
        Attendance, Attendance.id == AttendanceVerification.attendance_id,
    ).where(
        Attendance.user_id == attendance.user_id,
        AttendanceVerification.method == VerificationMethod.GPS,
        AttendanceVerification.is_valid.is_(True),
        AttendanceVerification.latitude == current.latitude,
        AttendanceVerification.longitude == current.longitude,
        AttendanceVerification.verified_at.between(
            current.verified_at - timedelta(minutes=15), current.verified_at,
        ),
    ))
    if burst >= 3 and "repeated_location_pattern" not in (attendance.review_reason or ""):
        attendance.flagged_for_review = True
        attendance.review_reason = ((attendance.review_reason + "; ") if attendance.review_reason else "") + \
            f"repeated_location_pattern:count={burst}"
        emit("attendance_abuse_signal", reason="repeated_location_pattern",
             attendance_id=str(attendance.id), event_id=str(attendance.event_id))
        db.commit()
    return attendance


def check_in(db: Session, event: Event, user: User, payload: AttendanceCheckIn) -> Attendance:
    now = datetime.now(UTC)
    if event.check_in_opens_at and now < as_utc(event.check_in_opens_at):
        raise HTTPException(status_code=409, detail="Check-in is not open")
    if event.check_in_closes_at and now > as_utc(event.check_in_closes_at):
        raise HTTPException(status_code=409, detail="Check-in is closed")
    existing = db.scalar(select(Attendance).where(
        Attendance.event_id == event.id, Attendance.user_id == user.id
    ))
    if existing:
        existing.flagged_for_review = True
        existing.review_reason = ((existing.review_reason + "; ") if existing.review_reason else "") + "duplicate_check_in"
        db.commit()
        return existing
    ticket = db.get(Ticket, payload.ticket_id) if payload.ticket_id else None
    if ticket and (ticket.event_id != event.id or ticket.attendee_id != user.id or ticket.status not in {TicketStatus.ACTIVE, TicketStatus.USED}):
        raise HTTPException(status_code=403, detail="Ticket is not valid for this attendee and event")
    evidence = location_evidence(event, payload)
    attendance = Attendance(event_id=event.id, user_id=user.id, ticket_id=ticket.id if ticket else None,
                            status=AttendanceStatus.CHECKED_IN, checked_in_at=now)
    db.add(attendance); db.flush()
    if event.geofence_enabled:
        if event.geofence_radius_meters is None:
            # Legacy events could be saved with geofencing enabled but no radius; every comparison
            # below is against that radius, so this would otherwise surface as a 500 at check-in.
            raise HTTPException(status_code=409, detail="This event's geofence is not fully configured; ask the organizer to set a check-in radius")
        if payload.latitude is None or payload.longitude is None or event.venue is None:
            raise HTTPException(status_code=422, detail="Location is required for geofence verification")
        distance = evidence["distance_meters"]
        valid = evidence["outcome"] == "verified"
        db.add(AttendanceVerification(
            attendance_id=attendance.id, method=VerificationMethod.GPS, is_valid=valid,
            verified_at=now, latitude=payload.latitude, longitude=payload.longitude,
            accuracy_meters=payload.accuracy_meters, reason=f"distance_meters={distance:.2f}",
        ))
        if valid:
            attendance.status = AttendanceStatus.GPS_VERIFIED
        else:
            attendance.flagged_for_review = True
            attendance.review_reason = location_guidance(evidence)
    record_location(db, event, user, evidence, operation="attendance check-in")
    db.commit()
    if event.geofence_enabled:
        calculate_attendance_confidence(db, attendance)
    audit(db, actor_id=user.id, community_id=event.community_id,
          action="attendance.checked_in", target_type="attendance", target_id=attendance.id,
          metadata={"event_id": str(event.id), "gps_submitted": payload.latitude is not None})
    award_qualified_attendance(db, attendance)
    evaluate_attendance_abuse(db, attendance)
    return attendance


def confirm_peer(db: Session, event: Event, confirmer: User, subject_id, confirmed: bool):
    if not event.peer_confirmation_enabled:
        raise HTTPException(status_code=409, detail="Peer confirmation is disabled")
    now = datetime.now(UTC)
    if event.peer_confirmation_deadline and now > as_utc(event.peer_confirmation_deadline):
        raise HTTPException(status_code=409, detail="Peer confirmation deadline has passed")
    confirmer_attendance = db.scalar(select(Attendance).where(
        Attendance.event_id == event.id, Attendance.user_id == confirmer.id,
        Attendance.status.notin_([AttendanceStatus.NOT_CHECKED_IN, AttendanceStatus.REJECTED]),
    ))
    subject = db.scalar(select(Attendance).where(
        Attendance.event_id == event.id, Attendance.user_id == subject_id
    ))
    eligibility = set(event.peer_eligibility_statuses) or {
        AttendanceStatus.CHECKED_IN.value, AttendanceStatus.GPS_VERIFIED.value,
        AttendanceStatus.QR_VERIFIED.value, AttendanceStatus.PEER_VERIFIED.value,
        AttendanceStatus.ORGANIZER_VERIFIED.value,
    }
    if (confirmer.id == subject_id or confirmer_attendance is None or subject is None
            or confirmer_attendance.status.value not in eligibility
            or subject.status.value not in eligibility):
        raise HTTPException(status_code=403, detail="Peer confirmation is not permitted")
    duplicate = db.scalar(select(PeerConfirmation.id).where(
        PeerConfirmation.event_id == event.id,
        PeerConfirmation.confirmer_id == confirmer.id,
        PeerConfirmation.subject_id == subject_id,
    ))
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="Peer confirmation already submitted")
    confirmation = PeerConfirmation(
        event_id=event.id, confirmer_id=confirmer.id, subject_id=subject_id,
        decision=PeerConfirmationDecision.CONFIRMED if confirmed else PeerConfirmationDecision.CANNOT_CONFIRM,
        submitted_at=datetime.now(UTC),
    )
    reciprocal = db.scalar(select(PeerConfirmation.id).where(
        PeerConfirmation.event_id == event.id,
        PeerConfirmation.confirmer_id == subject_id,
        PeerConfirmation.subject_id == confirmer.id,
        PeerConfirmation.decision == PeerConfirmationDecision.CONFIRMED,
    ))
    if reciprocal is not None:
        confirmation.suspicious = True
        subject.flagged_for_review = True
        subject.review_reason = "Reciprocal peer confirmations require organizer review"
    recent_confirmations = db.query(PeerConfirmation).filter_by(
        event_id=event.id,
        confirmer_id=confirmer.id,
        decision=PeerConfirmationDecision.CONFIRMED,
    ).count()
    if confirmed and recent_confirmations >= 3:
        confirmation.suspicious = True
        subject.flagged_for_review = True
        subject.review_reason = "Repeated peer confirmations require organizer review"
    db.add(confirmation)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="Peer confirmation already submitted") from exc
    if confirmed:
        count = db.query(PeerConfirmation).filter_by(
            event_id=event.id, subject_id=subject_id, decision=PeerConfirmationDecision.CONFIRMED
        ).count()
        if count >= event.confirmations_required:
            existing_signal = db.scalar(select(AttendanceVerification).where(
                AttendanceVerification.attendance_id == subject.id,
                AttendanceVerification.method == VerificationMethod.PEER,
            ))
            if existing_signal is None:
                db.add(AttendanceVerification(attendance_id=subject.id, method=VerificationMethod.PEER,
                                              is_valid=True, verified_at=datetime.now(UTC)))
    db.commit()
    if confirmed and count >= event.confirmations_required:
        calculate_attendance_confidence(db, subject)
        award_qualified_attendance(db, subject)
    return confirmation


def organizer_verify(db: Session, attendance: Attendance, organizer: User, approve: bool, reason: str):
    event = db.get(Event, attendance.event_id)
    if not event.organizer_verification_enabled:
        raise HTTPException(status_code=409, detail="Organizer verification is disabled")
    # Owner-scoped: an Organizer of this community who neither owns the event nor holds an active
    # attendance-verifier staff assignment on it has no authority here.
    require_event_staff_authority(db, event, organizer, staff_roles=EVENT_ATTENDANCE_STAFF_ROLES)
    signal = db.scalar(select(AttendanceVerification).where(
        AttendanceVerification.attendance_id == attendance.id,
        AttendanceVerification.method == VerificationMethod.ORGANIZER,
    ))
    if signal is not None and signal.is_valid == approve and signal.reason == reason:
        # A replay is also a reconciliation opportunity. Older deployments could retain a
        # valid organizer signal while the denormalized attendance status was still CHECKED_IN,
        # which made organizer analytics undercount verified attendance. Both downstream
        # operations are idempotent: confidence derives from stored signals and point/recognition
        # awards use stable unique keys.
        calculate_attendance_confidence(db, attendance)
        award_qualified_attendance(db, attendance)
        return attendance
    prior_decision = signal.is_valid if signal is not None else None
    prior_reason = signal.reason if signal is not None else None
    decided_at = datetime.now(UTC)
    if signal is None:
        signal = AttendanceVerification(
            attendance_id=attendance.id, method=VerificationMethod.ORGANIZER,
            is_valid=approve, verified_at=decided_at, verifier_id=organizer.id, reason=reason,
        )
        db.add(signal)
    else:
        signal.is_valid = approve
        signal.verified_at = decided_at
        signal.verifier_id = organizer.id
        signal.reason = reason
    ticket_was_activated = False
    if approve and attendance.ticket_id:
        ticket = db.get(Ticket, attendance.ticket_id)
        if ticket and ticket.status == TicketStatus.ACTIVE:
            ticket.status = TicketStatus.USED
            ticket.used_at = signal.verified_at
            ticket.validated_by_id = organizer.id
            ticket_was_activated = True
    attendance.flagged_for_review = False
    db.commit()
    calculate_attendance_confidence(db, attendance)
    decision = audit(db, actor_id=organizer.id, community_id=event.community_id,
          action="attendance.override", target_type="attendance", target_id=attendance.id,
          metadata={"approved": approve, "reason": reason,
                    "previous_approved": prior_decision, "previous_reason": prior_reason},
          commit=False)
    db.flush()
    if approve:
        award_qualified_attendance(db, attendance)
    _compensate_attendance_points(db, attendance, approve=approve, decision_key=str(decision.id))
    if not approve:
        # Recompute recognition inputs after the attendance count and point balance changed.
        # Recognition awards remain append-only history; this prevents new awards from being
        # granted from the rejected attendance while preserving prior audited achievements.
        evaluate_recognition(db, attendance.user_id, event.community_id)
    notify(db, attendance.user_id,
           "attendance_approved" if approve else "attendance_rejected",
           "Attendance verified" if approve else "Attendance rejected",
           (f"Your attendance at {event.title} was verified by the organizer."
            if approve else f"Your attendance at {event.title} was rejected: {reason}"),
           {"event_id": str(event.id), "attendance_id": str(attendance.id), "reason": reason},
           community_id=event.community_id,
           deduplication_key=f"attendance-decision:{decision.id}", commit=False)
    db.commit()
    if ticket_was_activated:
        audit(db, actor_id=organizer.id, community_id=event.community_id,
              action="ticket.used", target_type="ticket", target_id=attendance.ticket_id,
              metadata={"event_id": str(event.id), "method": "organizer"})
    return attendance


def qr_verify(db: Session, attendance: Attendance, ticket: Ticket, verifier: User) -> Attendance:
    event = db.get(Event, attendance.event_id)
    if not event.qr_attendance_enabled:
        raise HTTPException(status_code=409, detail="QR attendance verification is disabled")
    # Any role that works the door may scan; the tenant boundary and the community's suspension
    # state are still enforced first, so a foreign Organizer can never reach this event.
    require_event_staff_authority(db, event, verifier, staff_roles=EVENT_ADMISSION_STAFF_ROLES)
    if ticket.event_id != attendance.event_id or ticket.attendee_id != attendance.user_id:
        raise HTTPException(status_code=403, detail="Ticket does not match attendance")
    if ticket.status not in {TicketStatus.ACTIVE, TicketStatus.USED}:
        raise HTTPException(status_code=409, detail="Ticket is not valid for attendance")
    updated, added = record_qr_attendance(db, event, ticket, verifier)
    if updated.id != attendance.id:
        raise HTTPException(status_code=409, detail="Ticket attendance record conflict")
    if not added:
        attendance.flagged_for_review = True
        attendance.review_reason = "Duplicate QR verification requires organizer review"
        db.commit()
        return attendance
    ticket_was_active = ticket.status == TicketStatus.ACTIVE
    if ticket_was_active:
        ticket.status = TicketStatus.USED
        ticket.used_at = datetime.now(UTC)
        ticket.validated_by_id = verifier.id
    db.commit()
    calculate_attendance_confidence(db, attendance)
    award_qualified_attendance(db, attendance)
    audit(db, actor_id=verifier.id, community_id=event.community_id,
          action="attendance.verified", target_type="attendance", target_id=attendance.id,
          metadata={"event_id": str(event.id), "method": VerificationMethod.QR.value})
    if ticket_was_active:
        audit(db, actor_id=verifier.id, community_id=event.community_id,
              action="ticket.used", target_type="ticket", target_id=ticket.id,
              metadata={"event_id": str(event.id)})
    return attendance
