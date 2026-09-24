"""Tenant-scoped administration configuration API."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
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
from src.services.governance import manage_membership
from src.services.notification import audit

router = APIRouter(prefix="/admin/communities/{community_id}", tags=["admin"])
category_router = APIRouter(prefix="/admin/categories", tags=["admin"])
platform_router = APIRouter(prefix="/admin/platform", tags=["admin"])


@category_router.get("")
def list_categories(
    db: Annotated[Session, Depends(get_db)],
    active_only: bool = True,
):
    """List event categories. Public endpoint — no auth required.
    Pass active_only=false to include inactive categories (Super Admin use)."""
    stmt = select(EventCategory)
    if active_only:
        stmt = stmt.where(EventCategory.is_active.is_(True))
    stmt = stmt.order_by(EventCategory.name)
    categories = db.scalars(stmt).all()
    return [{"id": str(c.id), "slug": c.slug, "name": c.name, "is_active": c.is_active} for c in categories]


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


@router.get("/milestones")
def list_milestones(
    community_id: UUID, db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    require_admin(db, community_id, user)
    return [{"id": str(item.id), "name": item.name, "slug": item.slug, "is_active": item.is_active}
            for item in db.query(Milestone).filter(Milestone.community_id == community_id).order_by(Milestone.name)]


@router.post("/ranks", status_code=status.HTTP_201_CREATED)
def create_rank(
    community_id: UUID,
    payload: RankCreateInput,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    require_admin(db, community_id, user)
    for requirement in payload.requirements:
        if requirement.requirement_type not in {"badge", "milestone"}:
            continue
        model = Badge if requirement.requirement_type == "badge" else Milestone
        referenced = db.get(model, requirement.reference_id) if requirement.reference_id else None
        if referenced is None or referenced.community_id != community_id:
            raise HTTPException(status_code=422, detail="Rank requirement reference must belong to the community")
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


@router.get("/ranks")
def list_ranks(
    community_id: UUID, db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    require_admin(db, community_id, user)
    return [{"id": str(item.id), "name": item.name, "slug": item.slug,
             "minimum_points": item.minimum_points, "is_active": item.is_active}
            for item in db.query(Rank).filter(Rank.community_id == community_id).order_by(Rank.sort_order, Rank.name)]


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


@router.get("/badges")
def list_badges(
    community_id: UUID, db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    require_admin(db, community_id, user)
    return [{"id": str(item.id), "name": item.name, "slug": item.slug, "is_active": item.is_active}
            for item in db.query(Badge).filter(Badge.community_id == community_id).order_by(Badge.name)]


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
    membership = manage_membership(db, community_id, membership_id, user,
                                   "role_changed", payload.reason, MembershipRole(payload.role))
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


@router.get("/achievement-rules")
def list_achievement_rules(
    community_id: UUID, db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    require_admin(db, community_id, user)
    return [{"id": str(item.id), "name": item.name, "slug": item.slug, "is_active": item.is_active}
            for item in db.query(AchievementRule).filter(AchievementRule.community_id == community_id).order_by(AchievementRule.name)]


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


# ── Platform-wide admin endpoints (super_admin only) ─────────────────────────

@platform_router.get("/users")
def list_platform_users(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_platform_roles(PlatformRole.SUPER_ADMIN))],
    limit: int = 50,
    offset: int = 0,
):
    """List all platform users. Super Admin only."""
    from src.models import Profile
    rows = db.execute(
        select(User, Profile)
        .outerjoin(Profile, Profile.user_id == User.id)
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "role": u.role.value if hasattr(u.role, "value") else u.role,
            "username": p.username if p else None,
            "display_name": p.display_name if p else None,
            "is_active": u.is_active,
            "is_email_verified": u.email_verified_at is not None,
        }
        for u, p in rows
    ]


@platform_router.get("/communities")
def list_platform_communities(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_platform_roles(PlatformRole.SUPER_ADMIN))],
    limit: int = 50,
    offset: int = 0,
):
    """List all platform communities. Super Admin only."""
    from src.models import Community
    communities = db.scalars(
        select(Community).order_by(Community.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "slug": c.slug,
            "is_active": c.is_active,
            "is_public": c.is_public,
            "lifecycle_status": c.lifecycle_status.value,
        }
        for c in communities
    ]
