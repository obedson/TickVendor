"""Cross-cutting logging, request ID, and database policy tests."""

import json
import logging

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.config import Settings
from src.logging_config import JsonFormatter, SensitiveDataFilter
from src.main import create_app


def test_request_id_is_propagated_and_returned():
    client = TestClient(create_app())

    response = client.get("/health", headers={"X-Request-ID": "request-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "request-123"


def test_request_id_is_generated_when_absent():
    response = TestClient(create_app()).get("/health")

    assert response.headers["X-Request-ID"]


def test_sensitive_data_filter_redacts_nested_secrets():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg={"email": "member@example.com", "password": "secret", "nested": {"token": "abc"}},
        args=(),
        exc_info=None,
    )

    assert SensitiveDataFilter().filter(record)
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"]["email"] == "member@example.com"
    assert payload["message"]["password"] == "[REDACTED]"
    assert payload["message"]["nested"]["token"] == "[REDACTED]"


def test_production_rejects_sqlite_database():
    with pytest.raises(ValidationError, match="SQLite is not allowed"):
        Settings(
            environment="production",
            database_url="sqlite:///./production.db",
            secret_key="x" * 40,
        )


def test_production_accepts_server_database_url():
    production = Settings(
        environment="production",
        database_url="postgresql+psycopg://user:pass@db/tickeven",
        secret_key="x" * 40,
    )

    assert production.environment == "production"
