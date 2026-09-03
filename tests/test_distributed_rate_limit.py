"""Deterministic tests for the shared Redis rate limiter."""

import pytest
from fastapi import HTTPException
from redis.exceptions import ConnectionError

from src.security_middleware import RedisRateLimiter


def test_redis_limiter_uses_atomic_counter_and_expiry(monkeypatch):
    calls = []

    class FakeRedis:
        def incr(self, key):
            calls.append(("incr", key))
            return 1

        def expire(self, key, seconds):
            calls.append(("expire", key, seconds))

    monkeypatch.setattr(
        "src.security_middleware.Redis.from_url",
        lambda url, **kwargs: (calls.append(("connect", url, kwargs)) or FakeRedis()),
    )
    limiter = RedisRateLimiter("rediss://redis.example/0", limit=60, window_seconds=60)
    limiter.check("client:/health")
    assert calls == [
        ("connect", "rediss://redis.example/0", {
            "decode_responses": True, "socket_timeout": 1, "socket_connect_timeout": 1,
        }),
        ("incr", "tickvendor:rate:client:/health"),
        ("expire", "tickvendor:rate:client:/health", 60),
    ]


def test_redis_limiter_fails_closed_when_store_is_unavailable():
    limiter = RedisRateLimiter("redis://example")

    class BrokenRedis:
        def incr(self, key):
            raise ConnectionError("offline")

    limiter.redis = BrokenRedis()
    with pytest.raises(HTTPException) as rejected:
        limiter.check("security-sensitive")
    assert rejected.value.status_code == 503
