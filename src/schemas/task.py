"""Task API schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator

from src.models import TaskPriority, TaskType

# Per-type config keys that are allowed for each task kind.
_TASK_TYPE_CONFIG_KEYS: dict[str, set[str]] = {
    TaskType.GENERAL: set(),
    TaskType.VIDEO: {"video_url", "platform"},
    TaskType.SOCIAL_FOLLOW: {"platform", "handle", "profile_url"},
    TaskType.SURVEY: {"survey_url", "survey_title"},
    TaskType.REFERRAL: {"referral_target", "min_referrals"},
    TaskType.PHYSICAL: {"location", "instructions"},
}


class TaskCreateInput(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=2, max_length=5000)
    event_id: UUID | None = None
    due_at: datetime | None = None
    priority: TaskPriority = TaskPriority.NORMAL
    impact_point_reward: int = Field(default=0, ge=0, le=10000)
    verification_required: bool = True
    attachments: list[HttpUrl] = Field(default_factory=list, max_length=10)
    task_type: TaskType = TaskType.GENERAL
    task_config: dict[str, Any] = Field(default_factory=dict)
    required_evidence_types: list[str] = Field(default_factory=lambda: ["text"])

    @field_validator("task_config")
    @classmethod
    def validate_task_config(cls, v: dict, info: Any) -> dict:
        task_type = info.data.get("task_type", TaskType.GENERAL)
        allowed = _TASK_TYPE_CONFIG_KEYS.get(task_type, set())
        unknown = set(v.keys()) - allowed
        if unknown:
            raise ValueError(f"Unknown config keys for task type '{task_type}': {unknown}")
        return v

    @field_validator("required_evidence_types")
    @classmethod
    def validate_evidence_types(cls, v: list[str]) -> list[str]:
        allowed = {"text", "url", "attachment"}
        invalid = set(v) - allowed
        if invalid:
            raise ValueError(f"Invalid evidence types: {invalid}. Allowed: {allowed}")
        return v


class AssignmentInput(BaseModel):
    assignee_id: UUID


class SubmissionInput(BaseModel):
    evidence_text: str | None = Field(default=None, max_length=10000)
    evidence_url: HttpUrl | None = None
    evidence_attachments: list[HttpUrl] = Field(default_factory=list, max_length=10)


class VerificationInput(BaseModel):
    approve: bool


class TaskResponse(BaseModel):
    id: UUID
    community_id: UUID
    created_by_id: UUID
    title: str
    description: str
    event_id: UUID | None = None
    due_at: datetime | None = None
    priority: TaskPriority
    impact_point_reward: int
    verification_required: bool
    attachments: list[HttpUrl] = Field(default_factory=list)
    task_type: TaskType = TaskType.GENERAL
    task_config: dict[str, Any] = Field(default_factory=dict)
    required_evidence_types: list[str] = Field(default_factory=lambda: ["text"])
    status: str


class TaskAssignmentResponse(BaseModel):
    id: UUID
    task_id: UUID
    assignee_id: UUID
    status: str
    due_at: datetime | None
