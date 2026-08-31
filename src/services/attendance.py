"""Attendance check-in, geofence, and layered verification services."""

from datetime import UTC, datetime
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.authorization import require_community_role
from src.models import (
    Attendance,
    AttendanceStatus,
    AttendanceVerification,
    Event,
    MembershipRole,
    PeerConfirmation,
    PeerConfirmationDecision,
    Ticket,
    TicketStatus,
    User,
    VerificationMethod,
)
from src.schemas.attendance import AttendanceCheckIn
from src.services.event import as_utc
from src.services.notification import audit


def haversine_meters(lat1: Decimal, lon1: Decimal, lat2: Decimal, lon2: Decimal) -> float:
    phi1, phi2 = radians(float(lat1)), radians(float(lat2))
    dphi = radians(float(lat2 - lat1)); dlambda = radians(float(lon2 - lon1))
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 6_371_000 * 2 * asin(sqrt(a))


def calculate_attendance_confidence(db: Session, attendance: Attendance) -> Attendance:
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
    weights = {VerificationMethod.GPS: Decimal(40), VerificationMethod.QR: Decimal(50),
               VerificationMethod.PEER: Decimal(30), VerificationMethod.ORGANIZER: Decimal(100)}
    attendance.confidence_score = min(Decimal(100), sum((weights[item] for item in valid), Decimal(0)))
    precedence = ((VerificationMethod.ORGANIZER, AttendanceStatus.ORGANIZER_VERIFIED),
                  (VerificationMethod.QR, AttendanceStatus.QR_VERIFIED),
                  (VerificationMethod.GPS, AttendanceStatus.GPS_VERIFIED),
                  (VerificationMethod.PEER, AttendanceStatus.PEER_VERIFIED))
    attendance.status = next((status for method, status in precedence if method in valid),
                             AttendanceStatus.CHECKED_IN)
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
    return attendance


def confirm_peer(db: Session, event: Event, confirmer: User, subject_id, confirmed: bool):
    confirmer_attendance = db.scalar(select(Attendance).where(
        Attendance.event_id == event.id, Attendance.user_id == confirmer.id,
        Attendance.status.notin_([AttendanceStatus.NOT_CHECKED_IN, AttendanceStatus.REJECTED]),
    ))
    subject = db.scalar(select(Attendance).where(
        Attendance.event_id == event.id, Attendance.user_id == subject_id
    ))
    if confirmer.id == subject_id or confirmer_attendance is None or subject is None:
        raise HTTPException(status_code=403, detail="Peer confirmation is not permitted")
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
    return confirmation


def organizer_verify(db: Session, attendance: Attendance, organizer: User, approve: bool, reason: str):
    event = db.get(Event, attendance.event_id)
    require_community_role(db, event.community_id, organizer, MembershipRole.ORGANIZER)
    db.add(AttendanceVerification(
        attendance_id=attendance.id, method=VerificationMethod.ORGANIZER,
        is_valid=approve, verified_at=datetime.now(UTC), verifier_id=organizer.id, reason=reason,
    ))
    db.commit()
    calculate_attendance_confidence(db, attendance)
    audit(db, actor_id=organizer.id, community_id=event.community_id,
          action="attendance.override", target_type="attendance", target_id=attendance.id,
          metadata={"approved": approve, "reason": reason})
    return attendance


def qr_verify(db: Session, attendance: Attendance, ticket: Ticket, verifier: User) -> Attendance:
    if ticket.event_id != attendance.event_id or ticket.attendee_id != attendance.user_id:
        raise HTTPException(status_code=403, detail="Ticket does not match attendance")
    if ticket.status not in {TicketStatus.ACTIVE, TicketStatus.USED}:
        raise HTTPException(status_code=409, detail="Ticket is not valid for attendance")
    existing = db.scalar(select(AttendanceVerification).where(
        AttendanceVerification.attendance_id == attendance.id,
        AttendanceVerification.method == VerificationMethod.QR,
    ))
    if existing is None:
        db.add(AttendanceVerification(
            attendance_id=attendance.id,
            method=VerificationMethod.QR,
            is_valid=True,
            verified_at=datetime.now(UTC),
            verifier_id=verifier.id,
        ))
    db.commit()
    calculate_attendance_confidence(db, attendance)
    return attendance
