"""Email delivery abstraction with a deterministic local/test adapter."""

from dataclasses import dataclass, field
from typing import Protocol


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


_default_sender = InMemoryEmailSender()


def get_email_sender() -> EmailSender:
    """Dependency hook; production must replace this with a configured provider."""
    return _default_sender
