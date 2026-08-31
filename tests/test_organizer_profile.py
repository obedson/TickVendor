"""Public organizer profile tests."""
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import Community, Event, EventStatus, LocationType, Organization, Profile, User


def test_organizer_profile_splits_past_and_upcoming_published_events(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'organizer.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine); sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        organizer = User(email="organizer@example.com", password_hash="hash")
        organizer.profile = Profile(username="organizer", display_name="Grace Organizer", bio="Community host", photo_url="https://example.com/photo.png")
        db.add(organizer); db.flush()
        organization = Organization(owner_id=organizer.id, name="Org", slug="organizer-org")
        db.add(organization); db.flush()
        community = Community(organization_id=organization.id, name="Community", slug="organizer-community")
        db.add(community); db.flush(); now = datetime.now(UTC)
        common = {"community_id": community.id, "organizer_id": organizer.id, "description": "Event", "category": "community", "location_type": LocationType.ONLINE, "status": EventStatus.PUBLISHED}
        db.add_all([
            Event(**common, title="Past Event", slug="past-event", starts_at=now-timedelta(days=2), ends_at=now-timedelta(days=1)),
            Event(**common, title="Upcoming Event", slug="upcoming-event", starts_at=now+timedelta(days=1), ends_at=now+timedelta(days=2)),
            Event(**{**common, "status": EventStatus.DRAFT}, title="Draft Event", slug="draft-event", starts_at=now+timedelta(days=3), ends_at=now+timedelta(days=4)),
        ])
        db.commit(); organizer_id = organizer.id
    app = create_app()
    def override_get_db():
        with sessions() as db: yield db
    app.dependency_overrides[get_db] = override_get_db
    response = TestClient(app).get(f"/api/v1/profiles/organizers/{organizer_id}")
    assert response.status_code == 200, response.text
    data = response.json(); assert data["name"] == "Grace Organizer"; assert data["photo_url"]
    assert [event["title"] for event in data["past_events"]] == ["Past Event"]
    assert [event["title"] for event in data["upcoming_events"]] == ["Upcoming Event"]
    assert data["verification_status"] == "unverified"
    engine.dispose()
