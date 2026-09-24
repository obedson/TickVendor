"""Focused tests for auth refresh behavior.

Tests:
- Refresh returns new access + refresh tokens.
- Old refresh token is invalidated after rotation.
- Invalid refresh token returns 401 (triggers clean sign-out in frontend).
- Expired access token + valid refresh token allows re-authentication.
"""
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy import event as sa_event
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.notifications.email import InMemoryEmailSender, get_email_sender


def _make_client(tmp_path, db_name="refresh.db"):
    engine = create_engine(
        f"sqlite:///{tmp_path / db_name}", connect_args={"check_same_thread": False}
    )

    @sa_event.listens_for(engine, "connect")
    def enable_fk(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()
    sender = InMemoryEmailSender()
    app.dependency_overrides[get_email_sender] = lambda: sender

    def override_get_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), engine


def test_refresh_returns_new_tokens_and_invalidates_old(tmp_path):
    """Refresh rotates tokens; old refresh token is rejected after rotation."""
    client, engine = _make_client(tmp_path)

    reg = client.post("/api/v1/auth/register", json={
        "email": "refresh@example.com",
        "password": "refresh-password-123",
        "username": "refresh_user",
        "display_name": "Refresh User",
    })
    assert reg.status_code == 201
    original_refresh = reg.json()["refresh_token"]
    # Refresh with the original token.
    refresh_response = client.post("/api/v1/auth/refresh", json={"refresh_token": original_refresh})
    assert refresh_response.status_code == 200, refresh_response.text
    new_data = refresh_response.json()
    assert "access_token" in new_data
    assert "refresh_token" in new_data
    new_refresh = new_data["refresh_token"]
    new_access = new_data["access_token"]

    # Refresh sessions must rotate. Access JWTs may be byte-identical when
    # issued within the same second because their signed claims are identical.
    assert new_refresh != original_refresh
    assert new_access

    # Old refresh token must now be rejected (rotation invalidates it).
    old_refresh_response = client.post("/api/v1/auth/refresh", json={"refresh_token": original_refresh})
    assert old_refresh_response.status_code == 401, (
        f"Old refresh token should be rejected, got {old_refresh_response.status_code}"
    )

    # New refresh token must still work.
    second_refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert second_refresh.status_code == 200

    engine.dispose()


def test_invalid_refresh_token_returns_401(tmp_path):
    """An invalid/unknown refresh token returns 401 — frontend should sign out."""
    client, engine = _make_client(tmp_path, "invalid_refresh.db")

    response = client.post("/api/v1/auth/refresh", json={"refresh_token": "completely-invalid-refresh-token-00000001"})
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    engine.dispose()


def test_expired_access_token_with_valid_refresh_allows_reauth(tmp_path):
    """Simulate the frontend refresh-on-401 flow at the API level.

    Creates an expired JWT manually to verify that:
    1. The expired token is rejected with 401.
    2. The refresh endpoint issues a new valid access token.
    3. The new access token is accepted.
    """
    import uuid
    from datetime import UTC, datetime, timedelta

    import jwt

    from src.config import settings

    client, engine = _make_client(tmp_path, "expired_access.db")

    reg = client.post("/api/v1/auth/register", json={
        "email": "expired@example.com",
        "password": "expired-password-123",
        "username": "expired_user",
        "display_name": "Expired User",
    })
    assert reg.status_code == 201
    refresh_token = reg.json()["refresh_token"]
    user_id = reg.json()["user"]["id"]

    # Craft an already-expired JWT using the real secret.
    now = datetime.now(UTC)
    expired_payload = {
        "sub": user_id,
        "role": "participant",
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),  # expired 1 hour ago
        "jti": str(uuid.uuid4()),
    }
    expired_token = jwt.encode(
        expired_payload,
        settings.secret_key.get_secret_value(),
        algorithm="HS256",
    )

    # Expired token should be rejected by /auth/me.
    me_response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert me_response.status_code == 401, f"Expected 401 for expired token, got {me_response.status_code}"

    # Frontend would then call /auth/refresh to get a new access token.
    refresh_response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_response.status_code == 200
    new_access = refresh_response.json()["access_token"]

    # New access token should work.
    me_ok = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    assert me_ok.status_code == 200

    engine.dispose()
