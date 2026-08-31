"""Foundation recovery regression tests."""

from fastapi.testclient import TestClient
from sqlalchemy import text


def test_settings_load_with_safe_development_defaults():
    from src.config import settings

    assert settings.app_name == "TickEven"
    assert settings.environment == "development"
    assert settings.database_url.startswith("sqlite:///")
    assert settings.secret_key.get_secret_value()


def test_database_session_executes_query():
    from src.database import SessionLocal

    with SessionLocal() as session:
        assert session.execute(text("SELECT 1")).scalar_one() == 1


def test_application_exposes_health_endpoint():
    from src.main import app

    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_validation_errors_use_stable_envelope():
    from src.main import app

    response = TestClient(app).get("/health/validate", params={"value": 0})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert isinstance(body["error"]["details"], list)
