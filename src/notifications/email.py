"""Email delivery abstraction with a deterministic local/test adapter."""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class EmailMessage:
    recipient: str
    subject: str
    token: str


class EmailSender(Protocol):
    def send_token(self, recipient: str, subject: str, token: str) -> None: ...


@dataclass
class InMemoryEmailSender:
    messages: list[EmailMessage] = field(default_factory=list)

    def send_token(self, recipient: str, subject: str, token: str) -> None:
        self.messages.append(EmailMessage(recipient=recipient, subject=subject, token=token))


_default_sender = InMemoryEmailSender()


def get_email_sender() -> EmailSender:
    """Dependency hook; production must replace this with a configured provider."""
    return _default_sender
