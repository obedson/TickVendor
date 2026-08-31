"""Push delivery abstraction with a deterministic local/test adapter."""
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True)
class PushMessage:
    user_id: UUID
    title: str
    body: str
    data: dict[str, Any]


class PushSender(Protocol):
    def send(self, user_id: UUID, title: str, body: str, data: dict[str, Any]) -> None: ...


@dataclass
class InMemoryPushSender:
    messages: list[PushMessage] = field(default_factory=list)

    def send(self, user_id: UUID, title: str, body: str, data: dict[str, Any]) -> None:
        self.messages.append(PushMessage(user_id=user_id, title=title, body=body, data=data))


_default_sender = InMemoryPushSender()


def get_push_sender() -> PushSender:
    """Dependency hook; production must replace this with a configured provider."""
    return _default_sender
