"""Foundation recovery regression tests."""

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import configure_mappers


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


def test_user_profile_models_map_and_enforce_identity_constraints():
    import src.models  # noqa: F401
    from src.database import Base

    configure_mappers()
    assert {"users", "profiles"}.issubset(Base.metadata.tables)
    assert Base.metadata.tables["users"].c.email.unique
    assert Base.metadata.tables["profiles"].c.user_id.unique
    assert Base.metadata.tables["profiles"].c.username.unique


def test_organization_community_membership_models_map_with_tenant_constraints():
    import src.models  # noqa: F401
    from src.database import Base

    configure_mappers()
    assert {"organizations", "communities", "memberships"}.issubset(Base.metadata.tables)
    membership = Base.metadata.tables["memberships"]
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in membership.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("community_id", "user_id") in unique_columns
