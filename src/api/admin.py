"""Tenant-scoped administration configuration API."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.authorization import require_community_role, require_platform_roles
from src.database import get_db
from src.models import (
    AchievementRule,
    Badge,
    BadgeAward,
    EventCategory,
    Membership,
    MembershipRole,
    Milestone,
    MilestoneRequirement,
    PlatformRole,
    Rank,
    RankRequirement,
    User,
)
from src.schemas.admin import (
    AchievementRuleCreateInput,
    AchievementRuleUpdateInput,
    BadgeCreateInput,
    BadgeRevokeInput,
    EventCategoryCreateInput,
    EventCategoryUpdateInput,
    MembershipRoleUpdateInput,
    MilestoneCreateInput,
    RankCreateInput,
    RankUpdateInput,
)
from src.services.achievement import evaluate_condition
from src.services.notification import audit

router = APIRouter(prefix="/admin/communities/{community_id}", tags=["admin"])
category_router = APIRouter(prefix="/admin/categories", tags=["admin"])


@category_router.post("", status_code=status.HTTP_201_CREATED)
def create_category(
    payload: EventCategoryCreateInput,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_platform_roles(PlatformRole.SUPER_ADMIN))],
):
    category = EventCategory(**payload.model_dump())
    db.add(category)
    commit_or_conflict(db)
    return {"id": str(category.id), "slug": category.slug}


@category_router.patch("/{category_id}")
def update_category(
    category_id: UUID,
    payload: EventCategoryUpdateInput,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_platform_roles(PlatformRole.SUPER_ADMIN))],
):
    category = db.get(EventCategory, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Event category not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    db.commit()
    return {"id": str(category.id), "slug": category.slug}


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
    values = payload.model_dump(exclude={"requirements"})
    rank = Rank(community_id=community_id, **values)
    db.add(rank)
    db.flush()
    db.add_all(RankRequirement(rank_id=rank.id, **requirement.model_dump())
               for requirement in payload.requirements)
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


@router.patch("/ranks/{rank_id}")
def update_rank(
    community_id: UUID, rank_id: UUID, payload: RankUpdateInput,
    db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)],
):
    require_admin(db, community_id, user)
    rank = db.get(Rank, rank_id)
    if rank is None or rank.community_id != community_id:
        raise HTTPException(status_code=404, detail="Rank not found")
    values = payload.model_dump(exclude_unset=True)
    for field, value in values.items():
        setattr(rank, field, value)
    db.commit()
    audit(db, actor_id=user.id, community_id=community_id, action="rank.changed",
          target_type="rank", target_id=rank.id, metadata={"fields": sorted(values)})
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


@router.post("/badge-awards/{award_id}/revoke", status_code=204)
def revoke_badge_award(
    community_id: UUID, award_id: UUID, payload: BadgeRevokeInput,
    db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)],
):
    require_admin(db, community_id, user)
    award = db.get(BadgeAward, award_id)
    badge = db.get(Badge, award.badge_id) if award else None
    if award is None or badge is None or badge.community_id != community_id:
        raise HTTPException(status_code=404, detail="Badge award not found")
    if award.revoked_at is not None:
        raise HTTPException(status_code=409, detail="Badge award already revoked")
    award.revoked_at = datetime.now(UTC); award.revoke_reason = payload.reason
    db.commit()
    audit(db, actor_id=user.id, community_id=community_id, action="badge.revoked",
          target_type="badge_award", target_id=award.id,
          metadata={"reason": payload.reason, "user_id": str(award.user_id)})


@router.patch("/memberships/{membership_id}/role")
def update_membership_role(
    community_id: UUID, membership_id: UUID, payload: MembershipRoleUpdateInput,
    db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)],
):
    require_admin(db, community_id, user)
    membership = db.get(Membership, membership_id)
    if membership is None or membership.community_id != community_id:
        raise HTTPException(status_code=404, detail="Membership not found")
    if membership.user_id == user.id:
        raise HTTPException(status_code=409, detail="Administrators cannot change their own role")
    previous = membership.role.value; membership.role = MembershipRole(payload.role); db.commit()
    audit(db, actor_id=user.id, community_id=community_id, action="user.role_changed",
          target_type="membership", target_id=membership.id,
          metadata={"user_id": str(membership.user_id), "from": previous, "to": payload.role})
    return {"id": str(membership.id), "role": membership.role.value}


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


@router.patch("/achievement-rules/{rule_id}")
def update_achievement_rule(
    community_id: UUID,
    rule_id: UUID,
    payload: AchievementRuleUpdateInput,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    require_admin(db, community_id, user)
    rule = db.get(AchievementRule, rule_id)
    if rule is None or rule.community_id != community_id:
        raise HTTPException(status_code=404, detail="Achievement rule not found")
    rule.is_active = payload.is_active
    db.commit()
    audit(
        db,
        actor_id=user.id,
        community_id=community_id,
        action="achievement_rule.updated",
        target_type="achievement_rule",
        target_id=rule.id,
        metadata={"is_active": rule.is_active},
    )
    return {"id": str(rule.id), "slug": rule.slug, "is_active": rule.is_active}
