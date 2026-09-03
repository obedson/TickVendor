"""Private object storage adapters for event media."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class StoredObject:
    key: str
    url: str


class ObjectStorage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> StoredObject: ...
    def delete(self, key: str) -> None: ...


class LocalObjectStorage:
    def __init__(self, root: str = "uploads"):
        self.root = Path(root).resolve()

    def put(self, key: str, data: bytes, content_type: str) -> StoredObject:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError("Unsafe storage key")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredObject(key, f"/uploads/{key}")

    def delete(self, key: str) -> None:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError("Unsafe storage key")
        path.unlink(missing_ok=True)


class S3ObjectStorage:
    """S3-compatible private storage; objects are never made public."""

    def __init__(self, *, bucket: str, region: str | None = None, endpoint: str | None = None,
                 access_key: str | None = None, secret_key: str | None = None,
                 signed_url_ttl_seconds: int = 900, client=None):
        if not bucket:
            raise ValueError("STORAGE_BUCKET is required")
        if client is None:
            import boto3
            client = boto3.client("s3", region_name=region, endpoint_url=endpoint,
                                  aws_access_key_id=access_key, aws_secret_access_key=secret_key)
        self.client = client
        self.bucket = bucket
        self.signed_url_ttl_seconds = signed_url_ttl_seconds

    def put(self, key: str, data: bytes, content_type: str) -> StoredObject:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        url = self.client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=self.signed_url_ttl_seconds,
        )
        return StoredObject(key, url)

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


def event_cover_key(community_id: object, event_id: object, filename: str) -> str:
    safe = Path(filename).name
    return f"communities/{community_id}/events/{event_id}/cover/{safe}"
