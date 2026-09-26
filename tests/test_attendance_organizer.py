"""Organizer attendance verification test."""

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import (
    Attendance,
    AttendanceStatus,
    AttendanceVerification,
    Membership,
    MembershipRole,
    User,
    VerificationMethod,
)
from src.services.attendance import organizer_verify, qr_verify
from tests.test_database import create_event_context


def test_organizer_can_verify_attendance(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'organizer-attendance.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        organizer, community, event = create_event_context(db)
        attendee = User(email="manual-attendee@example.com", password_hash="hash")
        db.add(attendee); db.flush()
        db.add(Membership(community_id=community.id, user_id=organizer.id, role=MembershipRole.ORGANIZER))
        attendance = Attendance(event_id=event.id, user_id=attendee.id,
                                status=AttendanceStatus.CHECKED_IN, checked_in_at=datetime.now(UTC))
        db.add(attendance); db.commit()
        organizer_verify(db, attendance, organizer, True, "Confirmed at venue")

        # Recreate the historical contradiction observed on staging: the authoritative
        # organizer signal exists, but the denormalized status is stale. An idempotent replay
        # must repair it rather than returning early.
        attendance.status = AttendanceStatus.CHECKED_IN
        attendance.confidence_score = 0
        db.commit()
        organizer_verify(db, attendance, organizer, True, "Confirmed at venue")
        with pytest.raises(HTTPException) as conflict:
            organizer_verify(db, attendance, organizer, False, "Changed decision")
        assert conflict.value.status_code == 409
        assert attendance.status == AttendanceStatus.ORGANIZER_VERIFIED
        assert attendance.confidence_score == 100
        assert db.query(AttendanceVerification).filter_by(
            attendance_id=attendance.id,
            method=VerificationMethod.ORGANIZER,
        ).count() == 1
    engine.dispose()


def test_disabled_attendance_methods_and_unauthorized_qr_are_rejected(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'attendance-methods.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        organizer, community, event = create_event_context(db)
        attendee = User(email="method-attendee@example.com", password_hash="hash")
        outsider = User(email="method-outsider@example.com", password_hash="hash")
        db.add_all([attendee, outsider]); db.flush()
        db.add(Membership(community_id=community.id, user_id=organizer.id, role=MembershipRole.ORGANIZER))
        attendance = Attendance(event_id=event.id, user_id=attendee.id, status=AttendanceStatus.CHECKED_IN)
        from src.models import Ticket, TicketStatus, TicketType
        ticket_type = TicketType(event_id=event.id, name="Free", quantity=1)
        db.add_all([attendance, ticket_type]); db.flush()
        ticket = Ticket(public_id="METHODQR", qr_token="method-qr-token", event_id=event.id,
                        ticket_type_id=ticket_type.id, attendee_id=attendee.id, status=TicketStatus.ACTIVE)
        db.add(ticket); db.commit()
        with pytest.raises(HTTPException) as denied:
            qr_verify(db, attendance, ticket, outsider)
        assert denied.value.status_code == 403
        event.qr_attendance_enabled = False; db.commit()
        with pytest.raises(HTTPException) as disabled:
            qr_verify(db, attendance, ticket, organizer)
        assert disabled.value.status_code == 409
        event.organizer_verification_enabled = False; db.commit()
        with pytest.raises(HTTPException) as organizer_disabled:
            organizer_verify(db, attendance, organizer, True, "Seen")
        assert organizer_disabled.value.status_code == 409
    engine.dispose()
