"""Attendance anti-abuse checks."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import (
    Attendance,
    AttendanceStatus,
    PeerConfirmation,
    PeerConfirmationDecision,
    User,
)
from src.schemas.attendance import AttendanceCheckIn
from src.services.attendance import check_in, confirm_peer
from tests.test_database import create_event_context


def test_low_accuracy_location_is_flagged_for_review(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'attendance-abuse.db'}")
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    _owner, _community, event = create_event_context(session)
    attendee = User(email="low-accuracy@example.com", password_hash="hash")
    session.add(attendee)
    session.flush()
    event.geofence_enabled = True
    event.geofence_radius_meters = 100
    if event.venue is None:
        from src.models import Venue

        event.venue = Venue(
            name="Venue",
            address="Address",
            latitude=Decimal("9.0"),
            longitude=Decimal("7.0"),
        )
    else:
        event.venue.latitude = Decimal("9.0")
        event.venue.longitude = Decimal("7.0")
    session.commit()
    attendance = check_in(
        session,
        event,
        attendee,
        AttendanceCheckIn(
            latitude=Decimal("9.0"),
            longitude=Decimal("7.0"),
            accuracy_meters=Decimal(500),
        ),
    )
    assert attendance.flagged_for_review
    assert "accuracy" in attendance.review_reason.lower()
    session.close()
    engine.dispose()


def test_reciprocal_peer_confirmation_is_flagged_not_auto_rejected(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'peer-abuse.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        _owner, _community, event = create_event_context(session)
        first = User(email="first-peer@example.com", password_hash="hash")
        second = User(email="second-peer@example.com", password_hash="hash")
        session.add_all([first, second]); session.flush()
        session.add_all([
            Attendance(event_id=event.id, user_id=first.id, status=AttendanceStatus.CHECKED_IN),
            Attendance(event_id=event.id, user_id=second.id, status=AttendanceStatus.CHECKED_IN),
            PeerConfirmation(event_id=event.id, confirmer_id=second.id, subject_id=first.id,
                             decision=PeerConfirmationDecision.CONFIRMED,
                             submitted_at=datetime.now(UTC)),
        ])
        event.confirmations_required = 1
        session.commit()
        confirmation = confirm_peer(session, event, first, second.id, True)
        subject = session.query(Attendance).filter_by(event_id=event.id, user_id=second.id).one()
        assert confirmation.suspicious
        assert subject.flagged_for_review
        assert subject.status == AttendanceStatus.PEER_VERIFIED
    engine.dispose()
