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


def test_event_venue_staff_models_map_with_staff_uniqueness():
    import src.models  # noqa: F401
    from src.database import Base

    configure_mappers()
    assert {"events", "venues", "event_staff"}.issubset(Base.metadata.tables)
    staff = Base.metadata.tables["event_staff"]
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in staff.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("event_id", "user_id") in unique_columns


def test_ticket_order_payment_models_map_with_idempotency_constraints():
    import src.models  # noqa: F401
    from src.database import Base

    configure_mappers()
    required = {"ticket_types", "tickets", "orders", "payments"}
    assert required.issubset(Base.metadata.tables)
    assert Base.metadata.tables["tickets"].c.qr_token.unique
    assert Base.metadata.tables["orders"].c.reference.unique
    assert Base.metadata.tables["payments"].c.idempotency_key.unique


def test_attendance_verification_models_map_with_duplicate_prevention():
    import src.models  # noqa: F401
    from src.database import Base

    configure_mappers()
    required = {"attendances", "attendance_verifications", "peer_confirmations"}
    assert required.issubset(Base.metadata.tables)
    attendance = Base.metadata.tables["attendances"]
    peer = Base.metadata.tables["peer_confirmations"]
    assert any(
        tuple(column.name for column in constraint.columns) == ("event_id", "user_id")
        for constraint in attendance.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    )
    assert any(
        tuple(column.name for column in constraint.columns)
        == ("event_id", "confirmer_id", "subject_id")
        for constraint in peer.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    )


def test_task_assignment_submission_models_map_with_uniqueness():
    import src.models  # noqa: F401
    from src.database import Base

    configure_mappers()
    assert {"tasks", "task_assignments", "task_submissions"}.issubset(Base.metadata.tables)
    assignments = Base.metadata.tables["task_assignments"]
    assert any(
        tuple(column.name for column in constraint.columns) == ("task_id", "assignee_id")
        for constraint in assignments.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    )


def test_activity_contribution_and_impact_models_map_with_idempotency():
    import src.models  # noqa: F401
    from src.database import Base

    configure_mappers()
    assert {"activities", "contributions", "impact_transactions"}.issubset(Base.metadata.tables)
    assert Base.metadata.tables["impact_transactions"].c.idempotency_key.unique
