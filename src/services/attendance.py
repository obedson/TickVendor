"""Attendance check-in, geofence, and layered verification services."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.authorization import require_community_role
from src.models import (
    Attendance,
    AttendanceStatus,
    AttendanceVerification,
    Event,
    EventStaff,
    MembershipRole,
    PeerConfirmation,
    PeerConfirmationDecision,
    PlatformRole,
    PointRule,
    Ticket,
    TicketStatus,
    User,
    VerificationMethod,
)
from src.schemas.attendance import AttendanceCheckIn
from src.services.event import as_utc
from src.services.impact import award_points
from src.services.notification import audit
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
    if required and not required.issubset(valid):
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
    if attendance.status == AttendanceStatus.REJECTED or not required.issubset(valid):
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
    attendance = Attendance(event_id=event.id, user_id=user.id, ticket_id=ticket.id if ticket else None,
                            status=AttendanceStatus.CHECKED_IN, checked_in_at=now)
    db.add(attendance); db.flush()
    if event.geofence_enabled:
        if payload.latitude is None or payload.longitude is None or event.venue is None:
            raise HTTPException(status_code=422, detail="Location is required for geofence verification")
        distance = haversine_meters(payload.latitude, payload.longitude, event.venue.latitude, event.venue.longitude)
        low_accuracy = (
            payload.accuracy_meters is not None
            and payload.accuracy_meters > event.geofence_radius_meters
        )
        valid = distance <= event.geofence_radius_meters and not low_accuracy
        db.add(AttendanceVerification(
            attendance_id=attendance.id, method=VerificationMethod.GPS, is_valid=valid,
            verified_at=now, latitude=payload.latitude, longitude=payload.longitude,
            accuracy_meters=payload.accuracy_meters, reason=f"distance_meters={distance:.2f}",
        ))
        if valid:
            attendance.status = AttendanceStatus.GPS_VERIFIED
        else:
            attendance.flagged_for_review = True
            attendance.review_reason = (
                "Location accuracy is too low for automatic verification"
                if low_accuracy
                else "Location outside event geofence"
            )
    db.commit()
    if event.geofence_enabled:
        calculate_attendance_confidence(db, attendance)
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
    submitted_count = db.scalar(select(func.count()).select_from(PeerConfirmation).where(
        PeerConfirmation.event_id == event.id,
        PeerConfirmation.confirmer_id == confirmer.id,
    )) or 0
    if event.max_peer_confirmations is not None and submitted_count >= event.max_peer_confirmations:
        raise HTTPException(status_code=409, detail="Peer confirmation limit reached")
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
    require_community_role(db, event.community_id, organizer, MembershipRole.ORGANIZER)
    db.add(AttendanceVerification(
        attendance_id=attendance.id, method=VerificationMethod.ORGANIZER,
        is_valid=approve, verified_at=datetime.now(UTC), verifier_id=organizer.id, reason=reason,
    ))
    db.commit()
    calculate_attendance_confidence(db, attendance)
    award_qualified_attendance(db, attendance)
    audit(db, actor_id=organizer.id, community_id=event.community_id,
          action="attendance.override", target_type="attendance", target_id=attendance.id,
          metadata={"approved": approve, "reason": reason})
    return attendance


def qr_verify(db: Session, attendance: Attendance, ticket: Ticket, verifier: User) -> Attendance:
    event = db.get(Event, attendance.event_id)
    if not event.qr_attendance_enabled:
        raise HTTPException(status_code=409, detail="QR attendance verification is disabled")
    require_community_role(db, event.community_id, verifier, MembershipRole.ORGANIZER)
    if verifier.role != PlatformRole.SUPER_ADMIN and event.organizer_id != verifier.id:
        staff = db.scalar(select(EventStaff).where(
            EventStaff.event_id == event.id,
            EventStaff.user_id == verifier.id,
            EventStaff.is_active.is_(True),
        ))
        membership = require_community_role(db, event.community_id, verifier, MembershipRole.ORGANIZER)
        if staff is None and membership.role != MembershipRole.ADMIN:
            raise HTTPException(status_code=403, detail="QR attendance verification permission required")
    if ticket.event_id != attendance.event_id or ticket.attendee_id != attendance.user_id:
        raise HTTPException(status_code=403, detail="Ticket does not match attendance")
    if ticket.status not in {TicketStatus.ACTIVE, TicketStatus.USED}:
        raise HTTPException(status_code=409, detail="Ticket is not valid for attendance")
    existing = db.scalar(select(AttendanceVerification).where(
        AttendanceVerification.attendance_id == attendance.id,
        AttendanceVerification.method == VerificationMethod.QR,
    ))
    if existing is not None:
        attendance.flagged_for_review = True
        attendance.review_reason = "Duplicate QR verification requires organizer review"
        db.commit()
        return attendance
    db.add(AttendanceVerification(
        attendance_id=attendance.id,
        method=VerificationMethod.QR,
        is_valid=True,
        verified_at=datetime.now(UTC),
        verifier_id=verifier.id,
    ))
    db.commit()
    calculate_attendance_confidence(db, attendance)
    award_qualified_attendance(db, attendance)
    return attendance
