"""Email delivery abstraction with a deterministic local/test adapter."""

import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage as SMTPMessage
from typing import Protocol

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


@dataclass
class InMemoryEmailSender:
    messages: list[EmailMessage] = field(default_factory=list)

    def send(self, recipient: str, subject: str, body: str) -> None:
        self.messages.append(EmailMessage(recipient=recipient, subject=subject, body=body))

    def send_token(self, recipient: str, subject: str, token: str) -> None:
        self.messages.append(
            EmailMessage(recipient=recipient, subject=subject, body=token, token=token)
        )


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
        self.send(recipient, subject, token)


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
