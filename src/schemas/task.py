"""Task API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from src.models import TaskPriority


class TaskCreateInput(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=2, max_length=5000)
    event_id: UUID | None = None
    due_at: datetime | None = None
    priority: TaskPriority = TaskPriority.NORMAL
    impact_point_reward: int = Field(default=0, ge=0, le=10000)
    verification_required: bool = True


class AssignmentInput(BaseModel):
    assignee_id: UUID


class SubmissionInput(BaseModel):
    evidence_text: str | None = Field(default=None, max_length=10000)
    evidence_url: HttpUrl | None = None


class VerificationInput(BaseModel):
    approve: bool


class TaskResponse(TaskCreateInput):
    id: UUID
    community_id: UUID
    created_by_id: UUID
    status: str


class TaskAssignmentResponse(BaseModel):
    id: UUID
    task_id: UUID
    assignee_id: UUID
    status: str
    due_at: datetime | None
