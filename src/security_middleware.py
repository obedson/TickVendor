"""Basic in-process rate limiting and secure response headers."""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request
from redis import Redis
from redis.exceptions import RedisError

from src.config import settings


class RateLimiter:
    def __init__(self, limit: int = 60, window_seconds: int = 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        bucket = self._requests[key]
        while bucket and bucket[0] <= now - self.window_seconds:
            bucket.popleft()
        if len(bucket) >= self.limit:
            raise HTTPException(status_code=429, detail="Too many requests")
        bucket.append(now)


class RedisRateLimiter:
    """Atomic fixed-window limiter for horizontally scaled deployments."""

    def __init__(self, url: str, limit: int = 60, window_seconds: int = 60):
        self.redis = Redis.from_url(url, decode_responses=True, socket_timeout=1, socket_connect_timeout=1)
        self.limit = limit
        self.window_seconds = window_seconds

    def check(self, key: str) -> None:
        bucket = f"tickvendor:rate:{key}"
        try:
            count = self.redis.incr(bucket)
        except RedisError as exc:
            raise HTTPException(status_code=503, detail="Rate limiting service unavailable") from exc
        if count == 1:
            self.redis.expire(bucket, self.window_seconds)
        if count > self.limit:
            raise HTTPException(status_code=429, detail="Too many requests")


class LoginAttemptLimiter:
    def __init__(self, max_failures: int = 5, window_seconds: int = 900):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def _bucket(self, key: str) -> deque[float]:
        now = time.monotonic()
        bucket = self._failures[key]
        while bucket and bucket[0] <= now - self.window_seconds:
            bucket.popleft()
        return bucket

    def check(self, key: str) -> None:
        if len(self._bucket(key)) >= self.max_failures:
            raise HTTPException(status_code=429, detail="Too many failed login attempts")

    def record_failure(self, key: str) -> None:
        self._bucket(key).append(time.monotonic())

    def record_success(self, key: str) -> None:
        self._failures.pop(key, None)


rate_limiter = RedisRateLimiter(settings.redis_url) if settings.distributed_rate_limit_enabled and settings.redis_url else RateLimiter()
login_attempt_limiter = LoginAttemptLimiter()


def request_key(request: Request) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}:{request.url.path}"
