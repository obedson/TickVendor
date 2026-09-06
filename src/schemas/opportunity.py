"""Activity opportunity API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OpportunityCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=10000)
    activity_type: str = Field(min_length=2, max_length=80)
    dimension: str = Field(pattern="^(service|leadership|participation|contribution|execution)$")
    starts_at: datetime
    ends_at: datetime
    location: str | None = Field(default=None, max_length=500)
    capacity: int | None = Field(default=None, ge=1, le=100000)
    members_only: bool = True

    @model_validator(mode="after")
    def valid_window(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class OpportunityUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, min_length=10, max_length=10000)
    location: str | None = Field(default=None, max_length=500)
    capacity: int | None = Field(default=None, ge=1, le=100000)


class OpportunityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    community_id: UUID
    created_by_id: UUID
    title: str
    description: str
    activity_type: str
    dimension: str
    starts_at: datetime
    ends_at: datetime
    location: str | None
    capacity: int | None
    members_only: bool
    status: str


class RegistrationResponse(BaseModel):
    id: UUID
    opportunity_id: UUID
    participant_id: UUID
    status: str
