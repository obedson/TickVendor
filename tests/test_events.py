"""Event API integration and tenant-isolation tests."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import (
    AuditLog,
    Community,
    EventCategory,
    Membership,
    MembershipRole,
    Organization,
    User,
)
from src.security import create_access_token, hash_password


def setup_client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'events.db'}", connect_args={"check_same_thread": False})
    event.listen(engine, "connect", lambda connection, _record: connection.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        users = [
            User(email="organizer@example.com", password_hash=hash_password("organizer-password")),
            User(email="outsider@example.com", password_hash=hash_password("outsider-password")),
        ]
        db.add_all(users)
        db.flush()
        org = Organization(owner_id=users[0].id, name="Org", slug="events-org")
        db.add(org)
        db.flush()
        community = Community(organization_id=org.id, name="Community", slug="events-community")
        db.add(community)
        db.flush()
        db.add_all([
            Membership(community_id=community.id, user_id=users[0].id, role=MembershipRole.ORGANIZER),
            EventCategory(slug="technology", name="Technology"),
        ])
        db.commit()
        ids = community.id, users[0].id, users[1].id
    app = create_app()
    def override_get_db():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), engine, sessions, ids


def auth(user_id):
    return {"Authorization": f"Bearer {create_access_token(user_id, 'participant')}"}


def test_event_create_publish_discover_update_and_cross_tenant_denial(tmp_path):
    client, engine, _sessions, (community_id, organizer_id, outsider_id) = setup_client(tmp_path)
    now = datetime.now(UTC) + timedelta(days=1)
    payload = {
        "community_id": str(community_id),
        "title": "TickEven Summit",
        "description": "A detailed technology community event.",
        "category": "technology",
        "starts_at": now.isoformat(),
        "ends_at": (now + timedelta(hours=2)).isoformat(),
        "location_type": "physical",
        "venue": {"name": "Hall", "address": "1 Main Street", "city": "Abuja"},
    }
    created = client.post("/api/v1/events", json=payload, headers=auth(organizer_id))
    assert created.status_code == 201, created.text
    event_id = created.json()["id"]
    assert client.get("/api/v1/events").json() == []

    denied = client.patch(
        f"/api/v1/events/{event_id}", json={"title": "Hijacked"}, headers=auth(outsider_id)
    )
    assert denied.status_code == 403

    published = client.post(f"/api/v1/events/{event_id}/publish", headers=auth(organizer_id))
    assert published.status_code == 200
    discovered = client.get("/api/v1/events", params={"search": "summit", "category": "technology"})
    assert discovered.status_code == 200
    assert len(discovered.json()) == 1
    detail = client.get(f"/api/v1/events/{event_id}")
    assert detail.status_code == 200
    assert detail.json()["venue"]["city"] == "Abuja"
    with _sessions() as db:
        assert {item.action for item in db.query(AuditLog)} >= {"event.created", "event.published"}
    engine.dispose()
