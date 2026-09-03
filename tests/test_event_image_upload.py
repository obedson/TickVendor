"""Authorized event cover-image upload tests."""
from datetime import UTC, datetime, timedelta

from src.security import create_access_token
from tests.test_events import setup_client


def test_event_cover_upload_validates_content_and_ownership(tmp_path, monkeypatch):
    client, engine, _sessions, (community_id, organizer_id, outsider_id) = setup_client(tmp_path)
    monkeypatch.setattr("src.api.events.settings.storage_local_root", str(tmp_path / "uploads"))
    now = datetime.now(UTC) + timedelta(days=1)
    payload = {"community_id": str(community_id), "title": "Image Event",
               "description": "Event with a safe cover image", "category": "technology",
               "starts_at": now.isoformat(), "ends_at": (now + timedelta(hours=2)).isoformat(),
               "location_type": "online", "online_url": "https://example.com"}
    headers = lambda uid: {"Authorization": f"Bearer {create_access_token(uid, 'participant')}"}
    event_id = client.post('/api/v1/events', json=payload, headers=headers(organizer_id)).json()['id']
    png = b'\x89PNG\r\n\x1a\n' + b'content'
    denied = client.post(f'/api/v1/events/{event_id}/cover-image', headers=headers(outsider_id),
                         files={'upload': ('cover.png', png, 'image/png')})
    assert denied.status_code == 403
    spoofed = client.post(f'/api/v1/events/{event_id}/cover-image', headers=headers(organizer_id),
                          files={'upload': ('cover.png', b'not-png', 'image/png')})
    assert spoofed.status_code == 422
    uploaded = client.post(f'/api/v1/events/{event_id}/cover-image', headers=headers(organizer_id),
                           files={'upload': ('cover.png', png, 'image/png')})
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()['cover_image_url'].startswith('/uploads/communities/')
    engine.dispose()
