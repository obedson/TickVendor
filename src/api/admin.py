"""Tenant-scoped administration configuration API."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.authorization import require_community_role
from src.database import get_db
from src.models import (
    AchievementRule,
    Badge,
    MembershipRole,
    Milestone,
    MilestoneRequirement,
    Rank,
    User,
)
from src.schemas.admin import (
    AchievementRuleCreateInput,
    BadgeCreateInput,
    MilestoneCreateInput,
    RankCreateInput,
)
from src.services.achievement import evaluate_condition
from src.services.notification import audit

router = APIRouter(prefix="/admin/communities/{community_id}", tags=["admin"])


def require_admin(db: Session, community_id: UUID, user: User) -> None:
    require_community_role(db, community_id, user, MembershipRole.ADMIN)


def commit_or_conflict(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Configuration slug already exists") from exc


@router.post("/milestones", status_code=status.HTTP_201_CREATED)
def create_milestone(
    community_id: UUID,
    payload: MilestoneCreateInput,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    require_admin(db, community_id, user)
    milestone = Milestone(
        community_id=community_id,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        icon_url=payload.icon_url,
        reward_points=payload.reward_points,
    )
    db.add(milestone)
    db.flush()
    db.add_all(
        MilestoneRequirement(
            milestone_id=milestone.id,
            metric=requirement.metric,
            operator=requirement.operator,
            threshold=requirement.threshold,
        )
        for requirement in payload.requirements
    )
    commit_or_conflict(db)
    audit(
        db,
        actor_id=user.id,
        community_id=community_id,
        action="milestone.created",
        target_type="milestone",
        target_id=milestone.id,
        metadata={"slug": milestone.slug},
    )
    return {"id": str(milestone.id), "slug": milestone.slug}


@router.post("/ranks", status_code=status.HTTP_201_CREATED)
def create_rank(
    community_id: UUID,
    payload: RankCreateInput,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    require_admin(db, community_id, user)
    rank = Rank(community_id=community_id, **payload.model_dump())
    db.add(rank)
    commit_or_conflict(db)
    audit(
        db,
        actor_id=user.id,
        community_id=community_id,
        action="rank.created",
        target_type="rank",
        target_id=rank.id,
        metadata={"slug": rank.slug},
    )
    return {"id": str(rank.id), "slug": rank.slug}


@router.post("/badges", status_code=status.HTTP_201_CREATED)
def create_badge(
    community_id: UUID,
    payload: BadgeCreateInput,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    require_admin(db, community_id, user)
    try:
        evaluate_condition(payload.requirements, {})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    badge = Badge(community_id=community_id, **payload.model_dump())
    db.add(badge)
    commit_or_conflict(db)
    audit(
        db,
        actor_id=user.id,
        community_id=community_id,
        action="badge.created",
        target_type="badge",
        target_id=badge.id,
        metadata={"slug": badge.slug},
    )
    return {"id": str(badge.id), "slug": badge.slug}


@router.post("/achievement-rules", status_code=status.HTTP_201_CREATED)
def create_achievement_rule(
    community_id: UUID,
    payload: AchievementRuleCreateInput,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    require_admin(db, community_id, user)
    try:
        evaluate_condition(payload.condition_tree, {})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    rule = AchievementRule(community_id=community_id, **payload.model_dump())
    db.add(rule)
    commit_or_conflict(db)
    audit(
        db,
        actor_id=user.id,
        community_id=community_id,
        action="achievement_rule.created",
        target_type="achievement_rule",
        target_id=rule.id,
        metadata={"slug": rule.slug},
    )
    return {"id": str(rule.id), "slug": rule.slug}
