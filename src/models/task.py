"""Task definition, assignment, and evidence submission models."""

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class TaskPriority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TaskType(str, enum.Enum):
    """Supported task kinds. Each kind drives per-type config and evidence requirements."""
    GENERAL = "general"
    VIDEO = "video"           # Watch a video / YouTube link
    SOCIAL_FOLLOW = "social_follow"  # Follow/subscribe on a social platform
    SURVEY = "survey"         # Complete a survey
    REFERRAL = "referral"     # Invite/refer new members
    PHYSICAL = "physical"     # Physical/manual work (e.g. arranging chairs)


class TaskAssignmentStatus(str, enum.Enum):
    ASSIGNED = "assigned"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    VERIFIED = "verified"
    REJECTED = "rejected"
    OVERDUE = "overdue"


class Task(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_suspended", "is_suspended"),
        Index("ix_tasks_community_due", "community_id", "due_at"),
        Index("ix_tasks_search_title", "community_id", "is_active", "title"),
    )

    community_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("communities.id", ondelete="CASCADE"), nullable=False
    )
    event_id: Mapped[Any | None] = mapped_column(
        GUID(), ForeignKey("events.id", ondelete="SET NULL")
    )
    created_by_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority, native_enum=False, length=16),
        default=TaskPriority.NORMAL,
        nullable=False,
    )
    impact_point_reward: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    verification_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    attachments: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    # Task kind and per-type configuration (e.g. target URL, platform handle, survey link).
    task_type: Mapped[str] = mapped_column(
        String(32), default=TaskType.GENERAL.value, nullable=False
    )
    task_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # Which evidence types are required for submission (e.g. ["text"], ["url"], ["text","url"]).
    required_evidence_types: Mapped[list[str]] = mapped_column(
        JSON, default=lambda: ["text"], nullable=False
    )


class TaskAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "task_assignments"
    __table_args__ = (
        UniqueConstraint("task_id", "assignee_id", name="uq_task_assignment_assignee"),
        Index("ix_task_assignments_assignee_status", "assignee_id", "status"),
    )

    task_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    assignee_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    assigned_by_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[TaskAssignmentStatus] = mapped_column(
        Enum(TaskAssignmentStatus, native_enum=False, length=16),
        default=TaskAssignmentStatus.ASSIGNED,
        nullable=False,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by_id: Mapped[Any | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL")
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text)


class TaskSubmission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "task_submissions"
    __table_args__ = (Index("ix_task_submissions_assignment_submitted", "assignment_id", "submitted_at"),)

    assignment_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("task_assignments.id", ondelete="CASCADE"), nullable=False
    )
    evidence_text: Mapped[str | None] = mapped_column(Text)
    evidence_url: Mapped[str | None] = mapped_column(String(2048))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evidence_attachments: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
