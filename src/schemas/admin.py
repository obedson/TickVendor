"""Administrator-configurable recognition schemas."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class MetricRequirementInput(BaseModel):
    metric: str = Field(min_length=2, max_length=80)
    operator: Literal[">=", "<=", "="]
    threshold: int = Field(ge=0)


class MilestoneCreateInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str | None = Field(default=None, max_length=5000)
    icon_url: str | None = Field(default=None, max_length=2048)
    reward_points: int = Field(default=0, ge=0, le=100000)
    requirements: list[MetricRequirementInput] = Field(min_length=1, max_length=20)


class RankCreateInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str | None = Field(default=None, max_length=5000)
    icon_url: str | None = Field(default=None, max_length=2048)
    minimum_points: int = Field(ge=0)
    sort_order: int = Field(ge=0)
    requirements: list["RankRequirementInput"] = Field(default_factory=list, max_length=20)


class RankRequirementInput(BaseModel):
    requirement_type: Literal[
        "attendance_count", "task_count", "contribution_count", "service_activities",
        "leadership_activities", "peer_confirmations", "milestone", "badge",
    ]
    reference_id: UUID | None = None
    threshold: int = Field(default=1, ge=1)


class BadgeCreateInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str | None = Field(default=None, max_length=5000)
    icon_url: str | None = Field(default=None, max_length=2048)
    category: str = Field(min_length=2, max_length=64)
    requirements: dict[str, Any]
    reward_points: int = Field(default=0, ge=0, le=100000)
    is_visible: bool = True


class AchievementRuleCreateInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str | None = Field(default=None, max_length=5000)
    condition_tree: dict[str, Any]
    reward_definition: dict[str, Any]


class EventCategoryCreateInput(BaseModel):
    slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    is_active: bool = True


class EventCategoryUpdateInput(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    is_active: bool | None = None


class BadgeRevokeInput(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class MembershipRoleUpdateInput(BaseModel):
    role: Literal["member", "organizer", "admin"]


class RankUpdateInput(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    minimum_points: int | None = Field(default=None, ge=0)
    sort_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
