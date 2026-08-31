"""Authentication API integration tests."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app


def make_client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'auth.db'}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()

    def override_get_db():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), engine


def test_register_login_and_current_user_flow(tmp_path):
    client, engine = make_client(tmp_path)
    payload = {
        "email": "Member@Example.com",
        "password": "correct-horse-battery-staple",
        "username": "Member_1",
        "display_name": "Member One",
    }

    registration = client.post("/api/v1/auth/register", json=payload)
    assert registration.status_code == 201
    token = registration.json()["access_token"]
    assert registration.json()["user"]["email"] == "member@example.com"
    assert registration.json()["user"]["username"] == "member_1"

    duplicate = client.post("/api/v1/auth/register", json=payload)
    assert duplicate.status_code == 409

    bad_login = client.post(
        "/api/v1/auth/login", json={"email": payload["email"], "password": "wrong"}
    )
    assert bad_login.status_code == 401

    login = client.post(
        "/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]}
    )
    assert login.status_code == 200

    current = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert current.status_code == 200
    assert current.json()["username"] == "member_1"
    engine.dispose()


def test_registration_validates_password_and_username(tmp_path):
    client, engine = make_client(tmp_path)
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "valid@example.com",
            "password": "short",
            "username": "not valid!",
            "display_name": "Valid",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    engine.dispose()


def test_email_verification_refresh_rotation_logout_and_password_reset(tmp_path):
    from src.notifications.email import InMemoryEmailSender, get_email_sender

    client, engine = make_client(tmp_path)
    sender = InMemoryEmailSender()
    client.app.dependency_overrides[get_email_sender] = lambda: sender
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": "lifecycle@example.com",
            "password": "initial-password-123",
            "username": "lifecycle",
            "display_name": "Lifecycle",
        },
    )
    assert registration.status_code == 201
    refresh_token = registration.json()["refresh_token"]
    verification_token = sender.messages[-1].token

    verified = client.post("/api/v1/auth/verify-email", json={"token": verification_token})
    assert verified.status_code == 204

    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert rotated.status_code == 200
    new_refresh_token = rotated.json()["refresh_token"]
    assert new_refresh_token != refresh_token
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token}).status_code == 401

    logout = client.post("/api/v1/auth/logout", json={"refresh_token": new_refresh_token})
    assert logout.status_code == 204
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh_token}).status_code == 401

    reset_request = client.post(
        "/api/v1/auth/password-reset/request", json={"email": "lifecycle@example.com"}
    )
    assert reset_request.status_code == 202
    reset_token = sender.messages[-1].token
    reset = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": reset_token, "new_password": "replacement-password-456"},
    )
    assert reset.status_code == 204
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "lifecycle@example.com", "password": "initial-password-123"},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "lifecycle@example.com", "password": "replacement-password-456"},
    ).status_code == 200
    engine.dispose()
