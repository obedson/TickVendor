"""Attendance anti-abuse checks."""

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import User
from src.schemas.attendance import AttendanceCheckIn
from src.services.attendance import check_in
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
