"""Private object storage adapters for event media."""
from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import unquote, urlencode, urlsplit

from src.config import settings


@dataclass(frozen=True)
class StoredObject:
    key: str
    url: str


class ObjectStorage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> StoredObject: ...
    def get_url(self, key: str) -> str: ...
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

    def get_url(self, key: str) -> str:
        expires = int(time.time()) + settings.storage_signed_url_ttl_seconds
        return f"{settings.api_v1_prefix}/events/media/local?" + urlencode({
            "key": key, "expires": expires, "signature": local_signature(key, expires),
        })


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
        return StoredObject(key, f"s3://{self.bucket}/{key}")

    def get_url(self, key: str) -> str:
        return self.client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=self.signed_url_ttl_seconds,
        )

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


def event_cover_key(community_id: object, event_id: object, filename: str) -> str:
    safe = Path(filename).name
    return f"communities/{community_id}/events/{event_id}/cover/{safe}"


def get_object_storage() -> ObjectStorage:
    if settings.storage_provider == "s3":
        return S3ObjectStorage(
            bucket=settings.storage_bucket or "", region=settings.storage_region,
            endpoint=settings.storage_endpoint,
            access_key=settings.storage_access_key.get_secret_value() if settings.storage_access_key else None,
            secret_key=settings.storage_secret_key.get_secret_value() if settings.storage_secret_key else None,
            signed_url_ttl_seconds=settings.storage_signed_url_ttl_seconds,
        )
    return LocalObjectStorage(settings.storage_local_root)


def local_signature(key: str, expires: int) -> str:
    return hmac.new(settings.secret_key.get_secret_value().encode(),
                    f"event-cover:{key}:{expires}".encode(), hashlib.sha256).hexdigest()


def managed_cover_key(identity: str | None, community_id: object, event_id: object) -> str | None:
    if not identity:
        return None
    prefix = f"s3://{settings.storage_bucket}/" if settings.storage_provider == "s3" else "/uploads/"
    if identity.startswith(prefix):
        key = identity[len(prefix):]
    elif settings.storage_provider == "s3" and identity.startswith("https://"):
        # Recover pre-transition signed URLs only for our configured bucket/host.
        parsed = urlsplit(identity)
        endpoint = urlsplit(settings.storage_endpoint or "")
        bucket = settings.storage_bucket or ""
        path = unquote(parsed.path).lstrip('/')
        if endpoint.hostname and parsed.hostname == endpoint.hostname and path.startswith(bucket + '/'):
            key = path[len(bucket) + 1:]
        elif parsed.hostname in {
            f"{bucket}.s3.amazonaws.com", f"{bucket}.s3.{settings.storage_region}.amazonaws.com",
            f"{bucket}.{endpoint.hostname}" if endpoint.hostname else "",
        }:
            key = path
        else:
            return None
    else:
        return None
    expected = f"communities/{community_id}/events/{event_id}/cover/"
    if not key.startswith(expected) or '..' in key.split('/') or '\\' in key:
        return None
    return key


def cover_delivery_url(identity: str | None, community_id: object, event_id: object) -> str | None:
    key = managed_cover_key(identity, community_id, event_id)
    if key:
        return get_object_storage().get_url(key)
    # Preserve legacy external covers, but never deliver a storage URI to a browser.
    return identity if identity and identity.startswith(("https://", "http://")) else None
