"""Private S3-compatible object storage contract tests."""
from src.storage import S3ObjectStorage, event_cover_key


class FakeS3:
    def __init__(self):
        self.puts = []
        self.deletes = []

    def put_object(self, **payload):
        self.puts.append(payload)

    def generate_presigned_url(self, operation, Params, ExpiresIn):
        return f"https://private.example/{Params['Key']}?expires={ExpiresIn}"

    def delete_object(self, **payload):
        self.deletes.append(payload)


def test_s3_storage_is_private_tenant_scoped_and_deletable():
    client = FakeS3()
    storage = S3ObjectStorage(bucket="private-media", client=client)
    key = event_cover_key("community-a", "event-b", "../cover.png")
    stored = storage.put(key, b"png", "image/png")
    assert key == "communities/community-a/events/event-b/cover/cover.png"
    assert client.puts == [{"Bucket": "private-media", "Key": key, "Body": b"png", "ContentType": "image/png"}]
    # Persist the object identity, never the expiring delivery URL.
    assert stored.url == f"s3://private-media/{key}"
    assert "private.example" in storage.get_url(key)
    storage.delete(key)
    assert client.deletes == [{"Bucket": "private-media", "Key": key}]


def test_local_identity_delivery_and_containment(tmp_path):
    import pytest

    from src.storage import LocalObjectStorage, cover_delivery_url, managed_cover_key
    storage = LocalObjectStorage(str(tmp_path))
    key = event_cover_key('a', 'b', 'cover.png')
    assert storage.put(key, b'png', 'image/png').url == f'/uploads/{key}'
    assert 'signature=' in storage.get_url(key)
    assert managed_cover_key(f'/uploads/{key}', 'wrong-tenant', 'b') is None
    assert cover_delivery_url('s3://unknown/key', 'a', 'b') is None
    for operation in (lambda: storage.put('../escape', b'x', 'image/png'), lambda: storage.delete('../escape')):
        with pytest.raises(ValueError):
            operation()
    storage.delete(key)
    assert not (tmp_path / key).exists()


def test_s3_resolver_resigns_stable_and_legacy_identity(monkeypatch):
    from src.config import settings
    from src.storage import cover_delivery_url
    monkeypatch.setattr(settings, 'storage_provider', 's3')
    monkeypatch.setattr(settings, 'storage_bucket', 'private-media')
    monkeypatch.setattr(settings, 'storage_endpoint', 'https://account.r2.cloudflarestorage.com')
    storage = S3ObjectStorage(bucket='private-media', client=FakeS3())
    monkeypatch.setattr('src.storage.get_object_storage', lambda: storage)
    key = event_cover_key('a', 'b', 'cover.png')
    for identity in (f's3://private-media/{key}', f'https://account.r2.cloudflarestorage.com/private-media/{key}?X-Amz-Signature=expired'):
        assert cover_delivery_url(identity, 'a', 'b') == storage.get_url(key)
    assert cover_delivery_url(f's3://private-media/{key}', 'other-tenant', 'b') is None
    assert cover_delivery_url('https://external.example/cover.png', 'a', 'b') == 'https://external.example/cover.png'
