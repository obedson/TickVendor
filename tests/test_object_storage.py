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
    assert "private.example" in stored.url
    storage.delete(key)
    assert client.deletes == [{"Bucket": "private-media", "Key": key}]