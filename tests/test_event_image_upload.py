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
    delivery = uploaded.json()['cover_image_url']
    assert delivery.startswith('/api/v1/events/media/local?')
    assert client.get(delivery).content == png
    assert client.get(delivery.replace('signature=', 'signature=forged')).status_code == 403
    assert client.get(delivery.replace('signature=', 'signature=%C3%A9')).status_code == 403
    from urllib.parse import parse_qs, urlsplit
    from uuid import UUID

    from src.models import Event
    from src.storage import local_signature
    query = parse_qs(urlsplit(delivery).query)
    key = query['key'][0]
    assert key.startswith(f'communities/{community_id}/events/{event_id}/cover/')
    with _sessions() as db:
        assert db.get(Event, UUID(event_id)).cover_image_url == f'/uploads/{key}'
    expired = client.get('/api/v1/events/media/local', params={
        'key': key, 'expires': 1, 'signature': local_signature(key, 1)})
    assert expired.status_code == 403
    replaced = client.post(f'/api/v1/events/{event_id}/cover-image', headers=headers(organizer_id),
                          files={'upload': ('cover.png', png, 'image/png')})
    assert replaced.status_code == 200
    assert not (tmp_path / 'uploads' / key).exists()
    assert client.delete(f'/api/v1/events/{event_id}/cover-image', headers=headers(outsider_id)).status_code == 403
    assert client.delete(f'/api/v1/events/{event_id}/cover-image', headers=headers(organizer_id)).status_code == 204
    assert client.get(replaced.json()['cover_image_url']).status_code == 404
    with _sessions() as db:
        assert db.get(Event, UUID(event_id)).cover_image_url is None
    new_upload = client.post(f'/api/v1/events/{event_id}/cover-image', headers=headers(organizer_id),
                            files={'upload': ('cover.png', png, 'image/png')})
    assert client.patch(f'/api/v1/events/{event_id}', headers=headers(organizer_id),
                        json={'cover_image_url': 'https://example.com/external.png'}).status_code == 200
    assert client.get(new_upload.json()['cover_image_url']).status_code == 404
    engine.dispose()


def test_s3_cover_is_stable_in_database_and_renderable_in_all_responses(tmp_path, monkeypatch):
    from uuid import UUID

    from src.config import settings
    from src.models import Event
    from src.storage import S3ObjectStorage
    from tests.test_object_storage import FakeS3
    client, engine, sessions, (community_id, organizer_id, _) = setup_client(tmp_path)
    fake = FakeS3()
    storage = S3ObjectStorage(bucket='private-media', client=fake)
    monkeypatch.setattr(settings, 'storage_provider', 's3')
    monkeypatch.setattr(settings, 'storage_bucket', 'private-media')
    monkeypatch.setattr('src.storage.get_object_storage', lambda: storage)
    monkeypatch.setattr('src.api.events.get_object_storage', lambda: storage)
    headers = {'Authorization': f"Bearer {create_access_token(organizer_id, 'participant')}"}
    now = datetime.now(UTC) + timedelta(days=1)
    event_id = client.post('/api/v1/events', headers=headers, json={
        'community_id': str(community_id), 'title': 'Private cover event',
        'description': 'A detailed event story', 'category': 'technology',
        'starts_at': now.isoformat(), 'ends_at': (now + timedelta(hours=2)).isoformat(),
        'location_type': 'online', 'online_url': 'https://example.com',
    }).json()['id']
    response = client.post(f'/api/v1/events/{event_id}/cover-image', headers=headers,
                           files={'upload': ('cover.png', b'\x89PNG\r\n\x1a\ncontent', 'image/png')})
    assert response.status_code == 200, response.text
    url = response.json()['cover_image_url']
    assert url.startswith('https://private.example/communities/')
    assert len(fake.puts) == 1
    with sessions() as db:
        assert db.get(Event, UUID(event_id)).cover_image_url == f"s3://private-media/{fake.puts[0]['Key']}"
    published = client.post(f'/api/v1/events/{event_id}/publish', headers=headers)
    assert published.status_code == 200, published.text
    assert published.json()['cover_image_url'] == url
    assert client.get(f'/api/v1/events/{event_id}').json()['cover_image_url'] == url
    assert client.get('/api/v1/events').json()[0]['cover_image_url'] == url
    assert client.get('/api/v1/communities/organizer/events', headers=headers).json()[0]['cover_image_url'] == url
    assert client.delete(f'/api/v1/events/{event_id}/cover-image', headers=headers).status_code == 204
    assert fake.deletes == [{'Bucket': 'private-media', 'Key': fake.puts[0]['Key']}]
    engine.dispose()
