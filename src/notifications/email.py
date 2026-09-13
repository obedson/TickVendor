"""Email delivery abstraction with a deterministic local/test adapter."""

import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage as SMTPMessage
from typing import Protocol
from urllib.parse import quote

from src.config import settings


@dataclass(frozen=True)
class EmailMessage:
    recipient: str
    subject: str
    body: str
    token: str | None = None


class EmailSender(Protocol):
    def send(self, recipient: str, subject: str, body: str) -> None: ...

    def send_token(self, recipient: str, subject: str, token: str) -> None: ...


def verification_url(token: str) -> str:
    """Build the portable frontend verification URL without embedding a domain."""
    base_url = (settings.frontend_url or settings.canonical_url).rstrip("/")
    return f"{base_url}/verify-email?token={quote(token, safe='')}"


def verification_email_content(token: str) -> tuple[str, str]:
    """Return user-facing plain-text and HTML verification email bodies."""
    url = verification_url(token)
    text = (
        "Welcome to TickVendor.\n\n"
        "Verify your email address by opening this secure link:\n"
        f"{url}\n\n"
        "This link expires in 24 hours and can only be used once."
    )
    html = (
        "<p>Welcome to TickVendor.</p>"
        '<p>Verify your email address to finish creating your account.</p>'
        f'<p><a href="{url}">Verify your email address</a></p>'
        "<p>This link expires in 24 hours and can only be used once.</p>"
    )
    return text, html


def token_email_content(subject: str, token: str) -> tuple[str, str]:
    if subject != "Reset your TickVendor password":
        return verification_email_content(token)
    base = (settings.frontend_url or settings.canonical_url).rstrip("/")
    url = f"{base}/reset-password#token={quote(token, safe='')}"
    text = ("Reset your TickVendor password by opening this secure link:\n\n"
            + url + "\n\nThis link expires in 1 hour and can be used once. "
            "If you did not request this, ignore this email. Your password has not changed.")
    html = (f'<p>Reset your TickVendor password: <a href="{url}">Choose a new password</a>.</p>'
            '<p>This link expires in 1 hour and can be used once. If you did not request it, ignore this email.</p>')
    return text, html


@dataclass
class InMemoryEmailSender:
    messages: list[EmailMessage] = field(default_factory=list)

    def send(self, recipient: str, subject: str, body: str) -> None:
        self.messages.append(EmailMessage(recipient=recipient, subject=subject, body=body))

    def send_token(self, recipient: str, subject: str, token: str) -> None:
        text, _html = token_email_content(subject, token)
        self.messages.append(EmailMessage(recipient=recipient, subject=subject, body=text, token=token))


class SMTPEmailSender:
    """Environment-configured SMTP sender; credentials are never logged."""

    def __init__(self, host: str, port: int, username: str | None,
                 password: str | None, from_address: str):
        self.host, self.port = host, port
        self.username, self.password, self.from_address = username, password, from_address

    def send(self, recipient: str, subject: str, body: str) -> None:
        message = SMTPMessage()
        message["From"], message["To"], message["Subject"] = self.from_address, recipient, subject
        message.set_content(body)
        with smtplib.SMTP(self.host, self.port, timeout=10) as connection:
            connection.starttls()
            if self.username:
                connection.login(self.username, self.password or "")
            connection.send_message(message)

    def send_token(self, recipient: str, subject: str, token: str) -> None:
        text, html = token_email_content(subject, token)
        message = SMTPMessage()
        message["From"], message["To"], message["Subject"] = self.from_address, recipient, subject
        message.set_content(text)
        message.add_alternative(html, subtype="html")
        with smtplib.SMTP(self.host, self.port, timeout=10) as connection:
            connection.starttls()
            if self.username:
                connection.login(self.username, self.password or "")
            connection.send_message(message)


_default_sender = InMemoryEmailSender()


def get_email_sender() -> EmailSender:
    if settings.email_provider == "smtp":
        if not settings.smtp_host or not settings.smtp_from_address:
            raise RuntimeError("SMTP email provider is not configured")
        return SMTPEmailSender(
            settings.smtp_host, settings.smtp_port, settings.smtp_username,
            settings.smtp_password.get_secret_value() if settings.smtp_password else None,
            settings.smtp_from_address,
        )
    return _default_sender
