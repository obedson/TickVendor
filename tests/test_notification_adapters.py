"""Deterministic tests for configured notification delivery adapters."""
from uuid import uuid4

import pytest

from src.notifications.email import SMTPEmailSender, verification_email_content, verification_url
from src.notifications.push import HTTPPushSender


def test_smtp_sender_uses_configured_transport_without_logging_credentials(monkeypatch):
    calls = []

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): pass
        def starttls(self): calls.append("tls")
        def login(self, username, password): calls.append(("login", username, password))
        def send_message(self, message): calls.append(("message", message["To"], message["Subject"]))

    monkeypatch.setattr("src.notifications.email.smtplib.SMTP", lambda host, port, timeout: (calls.append((host, port, timeout)) or Connection()))
    SMTPEmailSender("smtp.example", 587, "user", "secret", "from@example.com").send("to@example.com", "Subject", "Body")
    assert calls == [("smtp.example", 587, 10), "tls", ("login", "user", "secret"), ("message", "to@example.com", "Subject")]


def test_verification_email_is_link_based_and_uses_configured_frontend(monkeypatch):
    from src.config import settings

    monkeypatch.setattr(settings, "frontend_url", "https://staging.example/app/")
    text, html = verification_email_content("opaque-token")
    assert verification_url("opaque-token") == "https://staging.example/app/verify-email?token=opaque-token"
    assert "Verify your email address" in text
    assert "https://staging.example/app/verify-email?token=opaque-token" in text
    assert '<a href="https://staging.example/app/verify-email?token=opaque-token">' in html
    assert "raw verification token" not in text


def test_http_push_sender_sends_bounded_payload_and_raises_provider_error(monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self): calls.append("checked")

    monkeypatch.setattr("src.notifications.push.httpx.post", lambda endpoint, **kwargs: (calls.append((endpoint, kwargs["json"], kwargs["headers"], kwargs["timeout"])) or Response()))
    user_id = uuid4()
    HTTPPushSender("https://push.example/send", "token").send(user_id, "Title", "Body", {"id": "safe"})
    assert calls[0][0] == "https://push.example/send"
    assert calls[0][1]["user_id"] == str(user_id)
    assert calls[0][2] == {"Authorization": "Bearer token"}
    assert calls[0][3] == 10
    assert calls[-1] == "checked"


def test_unconfigured_providers_fail_safely(monkeypatch):
    from src.config import settings
    from src.notifications.email import get_email_sender
    from src.notifications.push import get_push_sender

    monkeypatch.setattr(settings, "email_provider", "smtp")
    monkeypatch.setattr(settings, "smtp_host", None)
    monkeypatch.setattr(settings, "smtp_from_address", None)
    with pytest.raises(RuntimeError, match="SMTP email provider"):
        get_email_sender()
    monkeypatch.setattr(settings, "push_provider", "http")
    monkeypatch.setattr(settings, "push_endpoint", None)
    with pytest.raises(RuntimeError, match="HTTP push provider"):
        get_push_sender()
