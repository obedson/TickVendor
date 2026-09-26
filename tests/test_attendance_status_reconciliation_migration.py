"""Migration coverage for stale attendance status with valid organizer evidence."""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from src.config import settings
from src.models import (
    Attendance,
    AttendanceStatus,
    AttendanceVerification,
    User,
    VerificationMethod,
)
from tests.test_database import create_event_context


def test_migration_reconciles_only_status_derived_from_organizer_evidence(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'attendance-reconciliation.db'}"
    monkeypatch.setattr(settings, "database_url", database_url)
    config = Config("alembic.ini")
    command.upgrade(config, "f7a8b9c0d1e2")
    engine = sa.create_engine(database_url)
    with Session(engine, expire_on_commit=False) as db:
        owner, _community, event = create_event_context(db)
        attendee = User(email="migration-attendee@example.com", password_hash="hash")
        db.add(attendee)
        db.flush()
        attendance = Attendance(
            event_id=event.id,
            user_id=attendee.id,
            status=AttendanceStatus.CHECKED_IN,
            checked_in_at=datetime.now(UTC),
        )
        db.add(attendance)
        db.flush()
        db.add(AttendanceVerification(
            attendance_id=attendance.id,
            method=VerificationMethod.ORGANIZER,
            is_valid=True,
            verified_at=datetime.now(UTC),
            verifier_id=owner.id,
            reason="Confirmed at venue",
        ))
        db.commit()
        attendance_id = attendance.id
    engine.dispose()

    command.upgrade(config, "head")

    engine = sa.create_engine(database_url)
    with Session(engine) as db:
        repaired = db.get(Attendance, attendance_id)
        assert repaired.status == AttendanceStatus.ORGANIZER_VERIFIED
        assert repaired.confidence_score == 100
        assert db.query(AttendanceVerification).filter_by(
            attendance_id=attendance_id,
            method=VerificationMethod.ORGANIZER,
        ).count() == 1
    engine.dispose()
