"""Notification preference API schemas."""

from pydantic import BaseModel, Field


class NotificationPreferenceUpdate(BaseModel):
    in_app_enabled: bool | None = None
    email_enabled: bool | None = None
    push_enabled: bool | None = None
    muted_types: list[str] | None = Field(default=None, max_length=100)
