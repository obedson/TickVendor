"""Attendance service tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import (
    AttendanceVerification,
    ImpactTransaction,
    LocationType,
    PointRule,
    User,
    Venue,
    VerificationMethod,
)
from src.schemas.attendance import AttendanceCheckIn
from src.services.attendance import calculate_attendance_confidence, check_in, haversine_meters
from tests.test_database import create_event_context


def test_haversine_and_idempotent_geofence_checkin(tmp_path):
    assert haversine_meters(Decimal("9.0"), Decimal("7.0"), Decimal("9.0"), Decimal("7.0")) == 0
    engine = create_engine(f"sqlite:///{tmp_path / 'attendance.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        _owner, _community, event = create_event_context(db)
        attendee = User(email="attendee@example.com", password_hash="hash")
        venue = Venue(name="Venue", address="Address", latitude=Decimal("9.0"), longitude=Decimal("7.0"))
        db.add_all([attendee, venue]); db.flush()
        event.venue_id = venue.id; event.venue = venue; event.location_type = LocationType.PHYSICAL
        event.geofence_enabled = True; event.geofence_radius_meters = 100
        db.add(PointRule(source_type="attendance", points=10))
        event.check_in_opens_at = datetime.now(UTC) - timedelta(minutes=5)
        event.check_in_closes_at = datetime.now(UTC) + timedelta(minutes=5)
        db.commit()
        payload = AttendanceCheckIn(latitude=Decimal("9.0"), longitude=Decimal("7.0"))
        first = check_in(db, event, attendee, payload)
        second = check_in(db, event, attendee, payload)
        assert first.id == second.id
        assert first.status.value == "gps_verified"
        assert db.query(ImpactTransaction).filter_by(source_type="attendance").count() == 1
        assert second.flagged_for_review
        assert "duplicate_check_in" in second.review_reason
    engine.dispose()


def test_checkin_outside_window_is_rejected(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'closed.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        _owner, _community, event = create_event_context(db)
        attendee = User(email="late@example.com", password_hash="hash")
        db.add(attendee); db.flush()
        event.check_in_opens_at = datetime.now(UTC) + timedelta(hours=1)
        db.commit()
        with pytest.raises(HTTPException) as closed:
            check_in(db, event, attendee, AttendanceCheckIn())
        assert closed.value.status_code == 409
    engine.dispose()


def test_layered_signals_raise_confidence_and_organizer_rejection_wins(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'confidence.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        _owner, _community, event = create_event_context(db)
        attendee = User(email="confidence@example.com", password_hash="hash")
        db.add(attendee); db.flush()
        attendance = check_in(db, event, attendee, AttendanceCheckIn())
        db.add_all([
            AttendanceVerification(attendance_id=attendance.id, method=VerificationMethod.GPS,
                                   is_valid=True, verified_at=datetime.now(UTC)),
            AttendanceVerification(attendance_id=attendance.id, method=VerificationMethod.QR,
                                   is_valid=True, verified_at=datetime.now(UTC)),
        ]); db.commit()
        calculate_attendance_confidence(db, attendance)
        assert attendance.confidence_score == Decimal(90)
        assert attendance.status.value == "qr_verified"
        db.add(AttendanceVerification(attendance_id=attendance.id, method=VerificationMethod.ORGANIZER,
                                      is_valid=False, verified_at=datetime.now(UTC), reason="Denied")); db.commit()
        calculate_attendance_confidence(db, attendance)
        assert attendance.status.value == "rejected"
        assert attendance.confidence_score == 0
    engine.dispose()
