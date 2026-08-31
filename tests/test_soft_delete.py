"""Soft deletion tests for durable tenant resources."""
from datetime import UTC, datetime, timedelta

from src.models import AuditLog, Event
from src.security import create_access_token
from tests.test_events import setup_client


def test_event_soft_delete_is_authorized_hidden_audited_and_idempotent(tmp_path):
    client, engine, sessions, (community_id, organizer_id, outsider_id) = setup_client(tmp_path)
    now = datetime.now(UTC) + timedelta(days=1)
    payload = {
        "community_id": str(community_id), "title": "Disposable Event", "description": "Delete safely",
        "category": "technology", "starts_at": now.isoformat(),
        "ends_at": (now + timedelta(hours=2)).isoformat(), "location_type": "online",
        "online_url": "https://example.com/event",
    }
    headers = lambda user_id: {"Authorization": f"Bearer {create_access_token(user_id, 'participant')}"}
    created = client.post("/api/v1/events", json=payload, headers=headers(organizer_id))
    event_id = created.json()["id"]
    assert client.delete(f"/api/v1/events/{event_id}", headers=headers(outsider_id)).status_code == 403
    assert client.delete(f"/api/v1/events/{event_id}", headers=headers(organizer_id)).status_code == 204
    assert client.get(f"/api/v1/events/{event_id}").status_code == 404
    assert client.get("/api/v1/events", params={"search": "Disposable"}).json() == []
    assert client.delete(f"/api/v1/events/{event_id}", headers=headers(organizer_id)).status_code == 409
    with sessions() as db:
        event = db.get(Event, event_id)
        assert event.deleted_at is not None
        assert db.query(AuditLog).filter_by(action="event.deleted").count() == 1
    engine.dispose()
