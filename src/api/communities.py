"""Community analytics API."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.authorization import require_community_role
from src.database import get_db
from src.models import (
    Activity,
    Badge,
    Community,
    Contribution,
    Event,
    Membership,
    MembershipRole,
    MembershipStatus,
    Milestone,
    Rank,
    Task,
    User,
)
from src.services.analytics import community_summary, organizer_summary

router = APIRouter(prefix="/communities", tags=["communities"])


@router.get("/organizer/dashboard")
def organizer_dashboard(
    db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)],
):
    return organizer_summary(db, user)


@router.get("/{community_id}")
def detail(
    community_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    require_community_role(db, community_id, user, MembershipRole.MEMBER)
    community = db.get(Community, community_id)
    if community is None or community.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Community not found")

    def count(model, *criteria):
        return db.scalar(select(func.count()).select_from(model).where(*criteria))

    active_members = (
        Membership.community_id == community_id,
        Membership.status == MembershipStatus.ACTIVE,
    )
    return {
        "id": str(community.id),
        "name": community.name,
        "slug": community.slug,
        "logo_url": community.logo_url,
        "description": community.description,
        "counts": {
            "members": count(Membership, *active_members),
            "administrators": count(
                Membership,
                *active_members,
                Membership.role.in_([MembershipRole.ORGANIZER, MembershipRole.ADMIN]),
            ),
            "events": count(Event, Event.community_id == community_id, Event.deleted_at.is_(None)),
            "tasks": count(Task, Task.community_id == community_id),
            "activities": count(Activity, Activity.community_id == community_id),
            "contributions": count(Contribution, Contribution.community_id == community_id),
            "ranks": count(Rank, Rank.community_id == community_id),
            "badges": count(Badge, Badge.community_id == community_id),
            "milestones": count(Milestone, Milestone.community_id == community_id),
        },
    }


@router.get("/{community_id}/analytics")
def analytics(
    community_id: UUID, db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    return community_summary(db, community_id, user)
