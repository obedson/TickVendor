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
    assert client.post("/api/v1/auth/register", json=payload).status_code == 409
    assert client.post("/api/v1/auth/login", json={"email": payload["email"], "password": "wrong"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]}).status_code == 200
    current = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert current.status_code == 200
    assert current.json()["username"] == "member_1"
    engine.dispose()


def test_registration_validates_password_and_username(tmp_path):
    client, engine = make_client(tmp_path)
    response = client.post("/api/v1/auth/register", json={
        "email": "valid@example.com", "password": "short", "username": "not valid!", "display_name": "Valid",
    })
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    engine.dispose()


def test_email_verification_refresh_rotation_logout_and_password_reset(tmp_path):
    from src.notifications.email import InMemoryEmailSender, get_email_sender

    client, engine = make_client(tmp_path)
    sender = InMemoryEmailSender()
    client.app.dependency_overrides[get_email_sender] = lambda: sender
    registration = client.post("/api/v1/auth/register", json={
        "email": "lifecycle@example.com", "password": "initial-password-123", "username": "lifecycle", "display_name": "Lifecycle",
    })
    assert registration.status_code == 201
    refresh_token = registration.json()["refresh_token"]
    verification_token = sender.messages[-1].token
    assert client.post("/api/v1/auth/verify-email", json={"token": verification_token}).status_code == 204
    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert rotated.status_code == 200
    new_refresh_token = rotated.json()["refresh_token"]
    assert new_refresh_token != refresh_token
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token}).status_code == 401
    assert client.post("/api/v1/auth/logout", json={"refresh_token": new_refresh_token}).status_code == 204
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh_token}).status_code == 401
    assert client.post("/api/v1/auth/password-reset/request", json={"email": "lifecycle@example.com"}).status_code == 202
    reset_token = sender.messages[-1].token
    assert client.post("/api/v1/auth/password-reset/confirm", json={"token": reset_token, "new_password": "replacement-password-456"}).status_code == 204
    assert client.post("/api/v1/auth/login", json={"email": "lifecycle@example.com", "password": "initial-password-123"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "lifecycle@example.com", "password": "replacement-password-456"}).status_code == 200
    engine.dispose()


def test_registration_delivery_failure_rolls_back_account(tmp_path):
    from sqlalchemy import select

    from src.models import User
    from src.notifications.email import get_email_sender

    client, engine = make_client(tmp_path)

    class FailingSender:
        def send_token(self, recipient, subject, token):
            raise OSError("SMTP unavailable")

    client.app.dependency_overrides[get_email_sender] = lambda: FailingSender()
    response = client.post("/api/v1/auth/register", json={
        "email": "delivery-failure@example.com", "password": "initial-password-123",
        "username": "delivery_failure", "display_name": "Delivery Failure",
    })
    assert response.status_code == 503
    assert "account was not created" in response.json()["detail"]
    with engine.connect() as connection:
        assert connection.execute(select(User)).all() == []
    engine.dispose()


def test_resend_verification_delivers_new_token(tmp_path):
    from src.notifications.email import InMemoryEmailSender, get_email_sender

    client, engine = make_client(tmp_path)
    sender = InMemoryEmailSender()
    client.app.dependency_overrides[get_email_sender] = lambda: sender
    registration = client.post("/api/v1/auth/register", json={
        "email": "resend@example.com", "password": "initial-password-123", "username": "resend_user", "display_name": "Resend User",
    })
    assert registration.status_code == 201
    first_token = sender.messages[-1].token
    response = client.post("/api/v1/auth/verification/resend", json={"email": "RESEND@example.com"})
    assert response.status_code == 202
    second_token = sender.messages[-1].token
    assert second_token != first_token
    assert client.post("/api/v1/auth/verify-email", json={"token": first_token}).status_code == 204
    assert client.post("/api/v1/auth/verify-email", json={"token": second_token}).status_code == 204
    engine.dispose()


def test_smtp_timeout_rolls_back_all_registration_rows_and_allows_retry(tmp_path):
    from sqlalchemy import func, select

    from src.models import AuthSession, AuthToken, Profile, User
    from src.notifications.email import SMTPEmailSender, get_email_sender

    client, engine = make_client(tmp_path)
    client.app.dependency_overrides[get_email_sender] = lambda: SMTPEmailSender(
        "smtp.example", 587, "user", "secret", "from@example.com"
    )
    import src.notifications.email as email_module

    class TimeoutSMTP:
        def __init__(self, host, port, timeout):
            raise TimeoutError("SMTP timeout")

    original_smtp = email_module.smtplib.SMTP
    email_module.smtplib.SMTP = TimeoutSMTP
    try:
        failed = client.post(
            "/api/v1/auth/register",
            headers={"Origin": "http://localhost:3000"},
            json={
                "email": "retry@example.com", "password": "initial-password-123",
                "username": "retry_user", "display_name": "Retry User",
            },
        )
    finally:
        email_module.smtplib.SMTP = original_smtp
    assert failed.status_code == 503
    assert failed.headers["access-control-allow-origin"] == "http://localhost:3000"

    with engine.connect() as connection:
        for model in (User, Profile, AuthSession, AuthToken):
            assert connection.scalar(select(func.count()).select_from(model)) == 0

    from src.notifications.email import InMemoryEmailSender

    sender = InMemoryEmailSender()
    client.app.dependency_overrides[get_email_sender] = lambda: sender
    recovered = client.post("/api/v1/auth/register", json={
        "email": "retry@example.com", "password": "initial-password-123",
        "username": "retry_user", "display_name": "Retry User",
    })
    assert recovered.status_code == 201
    assert sender.messages[-1].token
    assert client.post("/api/v1/auth/register", json={
        "email": "retry@example.com", "password": "initial-password-123",
        "username": "retry_user", "display_name": "Retry User",
    }).status_code == 409
    engine.dispose()


def test_resend_is_only_for_active_unverified_accounts_and_failure_rolls_back(tmp_path):
    from sqlalchemy import select

    from src.models import AuthToken, User
    from src.notifications.email import InMemoryEmailSender, get_email_sender

    client, engine = make_client(tmp_path)
    sender = InMemoryEmailSender()
    client.app.dependency_overrides[get_email_sender] = lambda: sender
    registration = client.post("/api/v1/auth/register", json={
        "email": "resend-state@example.com", "password": "initial-password-123",
        "username": "resend_state", "display_name": "Resend State",
    })
    assert registration.status_code == 201
    token = sender.messages[-1].token
    assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 204
    before = len(sender.messages)
    assert client.post("/api/v1/auth/verification/resend", json={"email": "resend-state@example.com"}).status_code == 202
    assert len(sender.messages) == before

    class FailingSender:
        def send_token(self, recipient, subject, token):
            raise TimeoutError("SMTP timeout")

    unverified = client.post("/api/v1/auth/register", json={
        "email": "resend-failure@example.com", "password": "initial-password-123",
        "username": "resend_failure", "display_name": "Resend Failure",
    })
    assert unverified.status_code == 201
    client.app.dependency_overrides[get_email_sender] = lambda: FailingSender()
    failed = client.post("/api/v1/auth/verification/resend", json={"email": "resend-failure@example.com"})
    assert failed.status_code == 503
    with engine.connect() as connection:
        user = connection.execute(
            select(User.id, User.email_verified_at).where(User.email == "resend-failure@example.com")
        ).one()
        assert user.email_verified_at is None
        tokens = connection.scalars(select(AuthToken).where(AuthToken.user_id == user.id)).all()
        assert len(tokens) == 1
    engine.dispose()
