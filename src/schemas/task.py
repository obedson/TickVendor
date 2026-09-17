"""Task API schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator

from src.models import TaskPriority, TaskType
from src.services.task_assessment import validate_config
from src.services.task_location import LocationEvidence

# Per-type config keys that are allowed for each task kind.
_TASK_TYPE_CONFIG_KEYS: dict[str, set[str]] = {
    TaskType.GENERAL: set(),
    TaskType.VIDEO: {"video_url", "platform", "checkpoints"},
    TaskType.QUIZ: {"assessment"},
    TaskType.SOCIAL_FOLLOW: {"platform", "handle", "profile_url"},
    TaskType.SURVEY: {"survey_url", "survey_title", "assessment"},
    TaskType.REFERRAL: {"referral_target", "min_referrals"},
    TaskType.PHYSICAL: {"location", "instructions", "geofence"},
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
    task_config: dict[str, Any] = Field(default_factory=dict, validate_default=True)
    required_evidence_types: list[str] = Field(default_factory=lambda: ["text"])

    @field_validator("task_config")
    @classmethod
    def validate_task_config(cls, v: dict, info: Any) -> dict:
        task_type = info.data.get("task_type", TaskType.GENERAL)
        allowed = _TASK_TYPE_CONFIG_KEYS.get(task_type, set())
        unknown = set(v.keys()) - allowed
        if unknown:
            raise ValueError(f"Unknown config keys for task type '{task_type}': {unknown}")
        return validate_config(task_type, v)

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


class BulkResolveInput(BaseModel):
    emails: str | None = Field(default=None, max_length=100000)
    search: str = Field(default="", max_length=200)
    all_members: bool = False


class BulkAssignInput(BaseModel):
    selected_ids: list[UUID] = Field(default_factory=list, max_length=1000)
    all_members: bool = False
    selection_version: str | None = Field(default=None, max_length=64)


class SubmissionInput(BaseModel):
    attachment_ids: list[UUID] = Field(default_factory=list, max_length=10)
    location: LocationEvidence | None = None
    answers: dict[str, Any] = Field(default_factory=dict, max_length=30)
    idempotency_key: str | None = Field(default=None, min_length=16, max_length=160)
    evidence_text: str | None = Field(default=None, max_length=10000)
    evidence_url: HttpUrl | None = None
    evidence_attachments: list[HttpUrl] = Field(default_factory=list, max_length=10)


class VerificationInput(BaseModel):
    approve: bool
    reason: str | None = Field(default=None, max_length=1000)


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
    assessment_result: dict[str, Any] = Field(default_factory=dict)
    id: UUID
    task_id: UUID
    assignee_id: UUID
    status: str
    due_at: datetime | None
