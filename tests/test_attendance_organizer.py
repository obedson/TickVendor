"""Organizer attendance verification test."""

from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import Attendance, AttendanceStatus, Membership, MembershipRole, User
from src.services.attendance import organizer_verify
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
        assert attendance.status == AttendanceStatus.ORGANIZER_VERIFIED
    engine.dispose()
