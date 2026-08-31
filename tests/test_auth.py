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
