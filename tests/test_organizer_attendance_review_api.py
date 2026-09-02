"""Organizer attendance review API tests."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import (
    Attendance,
    AttendanceReviewStatus,
    AttendanceStatus,
    Membership,
    MembershipRole,
)
from src.security import create_access_token
from tests.test_database import create_event_context


def test_organizer_can_resolve_flagged_attendance_review(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'review.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        organizer, community, event = create_event_context(db)
        db.add(Membership(community_id=community.id, user_id=organizer.id, role=MembershipRole.ORGANIZER))
        attendance = Attendance(event_id=event.id, user_id=organizer.id, status=AttendanceStatus.CHECKED_IN,
                                flagged_for_review=True, review_reason="duplicate_check_in", review_status=AttendanceReviewStatus.OPEN,
                                checked_in_at=datetime.now(UTC))
        db.add(attendance); db.commit(); organizer_id, event_id, attendance_id = organizer.id, event.id, attendance.id
    app = create_app()
    def override():
        with sessions() as db: yield db
    app.dependency_overrides[get_db] = override
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {create_access_token(organizer_id, 'organizer')}"}
    listed = client.get(f"/api/v1/events/{event_id}/attendance/review", headers=headers)
    assert listed.status_code == 200 and listed.json()[0]["suspicious_signal_count"] == 1
    resolved = client.post(f"/api/v1/events/{event_id}/attendance/{attendance_id}/review", headers=headers,
                           json={"outcome": "confirmed", "reason": "Evidence reviewed"})
    assert resolved.status_code == 200 and resolved.json()["review_status"] == "confirmed"
    assert client.get(f"/api/v1/events/{event_id}/attendance/review", headers=headers).json() == []
    engine.dispose()
