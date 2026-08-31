"""Authentication abuse-prevention tests."""
import pytest
from fastapi import HTTPException

from src.security_middleware import LoginAttemptLimiter


def test_login_attempt_limiter_blocks_repeated_failures_and_resets_after_success():
    limiter = LoginAttemptLimiter(max_failures=3, window_seconds=60)
    key = "127.0.0.1:user@example.com"
    limiter.record_failure(key)
    limiter.record_failure(key)
    limiter.check(key)
    limiter.record_failure(key)
    with pytest.raises(HTTPException) as blocked:
        limiter.check(key)
    assert blocked.value.status_code == 429
    limiter.record_success(key)
    limiter.check(key)


def test_login_attempt_limiter_separates_accounts_and_does_not_count_success():
    limiter = LoginAttemptLimiter(max_failures=1, window_seconds=60)
    limiter.record_failure("127.0.0.1:first@example.com")
    limiter.check("127.0.0.1:second@example.com")
    limiter.record_success("127.0.0.1:second@example.com")
    limiter.check("127.0.0.1:second@example.com")
