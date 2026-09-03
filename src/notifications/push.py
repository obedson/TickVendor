"""Push delivery abstraction with a deterministic local/test adapter."""
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

import httpx

from src.config import settings


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


class HTTPPushSender:
    """Generic provider adapter for a configured push gateway."""

    def __init__(self, endpoint: str, api_token: str | None):
        self.endpoint, self.api_token = endpoint, api_token

    def send(self, user_id: UUID, title: str, body: str, data: dict[str, Any]) -> None:
        headers = {"Authorization": f"Bearer {self.api_token}"} if self.api_token else {}
        response = httpx.post(self.endpoint, json={"user_id": str(user_id), "title": title,
                           "body": body, "data": data}, headers=headers, timeout=10)
        response.raise_for_status()


_default_sender = InMemoryPushSender()


def get_push_sender() -> PushSender:
    if settings.push_provider == "http":
        if not settings.push_endpoint:
            raise RuntimeError("HTTP push provider is not configured")
        return HTTPPushSender(settings.push_endpoint,
                              settings.push_api_token.get_secret_value() if settings.push_api_token else None)
    return _default_sender
