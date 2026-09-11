"""Authenticated profile and journey summary API."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.database import get_db
from src.models import (
    Badge,
    BadgeAward,
    Event,
    EventStatus,
    ImpactTransaction,
    ImpactTransactionStatus,
    Membership,
    MembershipStatus,
    Milestone,
    MilestoneAward,
    ProfileVisibility,
    Rank,
    RankProgression,
    TaskAssignment,
    TaskAssignmentStatus,
    User,
)
from src.security import decode_access_token
from src.services.recognition import (
    current_rank,
    next_rank,
    qualified_attendance_count,
    user_metrics,
)

router = APIRouter(prefix="/profiles", tags=["profiles"])
optional_bearer = HTTPBearer(auto_error=False)


def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(optional_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User | None:
    if credentials is None:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        return db.get(User, UUID(payload["sub"]))
    except (KeyError, ValueError):
        return None


class ProfileUpdateInput(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    bio: str | None = Field(default=None, max_length=5000)
    location: str | None = Field(default=None, max_length=255)
    photo_url: str | None = Field(default=None, max_length=2048)
    visibility: ProfileVisibility | None = None


@router.get("/organizers/{user_id}")
def organizer_profile(user_id: UUID, db: Annotated[Session, Depends(get_db)]):
    user = db.get(User, user_id)
    if user is None or user.profile is None or user.profile.visibility == ProfileVisibility.PRIVATE:
        raise HTTPException(status_code=404, detail="Organizer not found")
    events = list(db.scalars(select(Event).where(
        Event.organizer_id == user_id, Event.status == EventStatus.PUBLISHED
    ).order_by(Event.starts_at)))
    if not events:
        raise HTTPException(status_code=404, detail="Organizer not found")
    now = datetime.now(UTC)
    serialize = lambda event: {
        "id": str(event.id), "title": event.title,
        "starts_at": event.starts_at.isoformat(), "ends_at": event.ends_at.isoformat(),
    }
    past = [serialize(event) for event in events if event.ends_at.replace(tzinfo=event.ends_at.tzinfo or UTC) < now]
    upcoming = [serialize(event) for event in events if event.ends_at.replace(tzinfo=event.ends_at.tzinfo or UTC) >= now]
    return {
        "name": user.profile.display_name,
        "username": user.profile.username,
        "photo_url": user.profile.photo_url,
        "description": user.profile.bio,
        "verification_status": "verified" if user.email_verified_at else "unverified",
        "events": past + upcoming,
        "past_events": past,
        "upcoming_events": upcoming,
    }


@router.get("/me")
def my_profile(
    db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)],
    community_id: UUID | None = None,
):
    if community_id is None:
        points = db.scalar(select(func.coalesce(func.sum(ImpactTransaction.points), 0)).where(
            ImpactTransaction.user_id == user.id,
            ImpactTransaction.status == ImpactTransactionStatus.POSTED,
        ))
        # Aggregate badges and milestones across all communities for the dashboard summary
        all_badges = list(db.execute(
            select(BadgeAward, Badge).join(Badge, Badge.id == BadgeAward.badge_id).where(
                BadgeAward.user_id == user.id, BadgeAward.revoked_at.is_(None)
            )
        ))
        all_milestones = list(db.execute(
            select(MilestoneAward, Milestone).join(Milestone, Milestone.id == MilestoneAward.milestone_id).where(
                MilestoneAward.user_id == user.id
            )
        ))
        # Attendance count across all communities
        events_attended = qualified_attendance_count(db, user.id)
        tasks_completed = db.scalar(select(func.count()).select_from(TaskAssignment).where(
            TaskAssignment.assignee_id == user.id,
            TaskAssignment.status == TaskAssignmentStatus.VERIFIED,
        )) or 0
        # Rank is community-scoped; omit it from the cross-community summary to avoid
        # misleading the caller with a rank from an unrelated community context.
        return {
            "id": str(user.id),
            "username": user.profile.username,
            "display_name": user.profile.display_name,
            "visibility": user.profile.visibility.value,
            "bio": user.profile.bio,
            "location": user.profile.location,
            "photo_url": user.profile.photo_url,
            "impact_points": points,
            "rank": None,
            "next_rank": None,
            "badges": [{"id": str(award.id), "name": badge.name, "icon_url": badge.icon_url} for award, badge in all_badges],
            "milestones": [{"id": str(award.id), "name": milestone.name} for award, milestone in all_milestones],
            "events_attended": events_attended,
            "tasks_completed": tasks_completed,
        }
    membership = db.scalar(select(Membership).where(
        Membership.community_id == community_id, Membership.user_id == user.id,
        Membership.status == MembershipStatus.ACTIVE,
    ))
    if membership is None:
        raise HTTPException(status_code=403, detail="Active community membership required")
    metrics = user_metrics(db, user.id, community_id)
    rank = current_rank(db, user.id, community_id)
    upcoming_rank = next_rank(db, user.id, community_id)
    badges = list(db.execute(select(BadgeAward, Badge).join(Badge, Badge.id == BadgeAward.badge_id).where(
        BadgeAward.user_id == user.id, Badge.community_id == community_id, BadgeAward.revoked_at.is_(None)
    )))
    milestones = list(db.execute(select(MilestoneAward, Milestone).join(
        Milestone, Milestone.id == MilestoneAward.milestone_id
    ).where(MilestoneAward.user_id == user.id, Milestone.community_id == community_id)))
    rank_history = list(db.execute(select(RankProgression, Rank).join(
        Rank, Rank.id == RankProgression.rank_id
    ).where(RankProgression.user_id == user.id, RankProgression.community_id == community_id)
      .order_by(RankProgression.achieved_at)))
    timeline = [{"type": "joined_community", "occurred_at": (membership.joined_at or membership.created_at).isoformat()}]
    timeline += [{"type": "badge_awarded", "name": badge.name, "occurred_at": award.awarded_at.isoformat()}
                 for award, badge in badges]
    timeline += [{"type": "milestone_awarded", "name": milestone.name,
                  "occurred_at": award.awarded_at.isoformat()} for award, milestone in milestones]
    dimensions = {"participation": metrics["attendance_count"], "execution": metrics["task_count"],
                  "contribution": metrics["contribution_count"], "service": metrics["service_activities"],
                  "leadership": metrics["leadership_activities"]}
    return {"id": str(user.id), "username": user.profile.username,
            "display_name": user.profile.display_name, "photo_url": user.profile.photo_url,
            "visibility": user.profile.visibility.value, "impact_points": metrics["impact_points"],
            "rank": {"id": str(rank.id), "name": rank.name} if rank else None,
            "rank_history": [{"name": item.name, "achieved_at": progression.achieved_at.isoformat()}
                             for progression, item in rank_history],
            "next_rank": ({"id": str(upcoming_rank.id), "name": upcoming_rank.name,
                           "minimum_points": upcoming_rank.minimum_points,
                           "points_remaining": max(0, upcoming_rank.minimum_points - metrics["impact_points"])}
                          if upcoming_rank else None),
            "badges": [{"name": badge.name, "icon_url": badge.icon_url} for _award, badge in badges],
            "milestones": [{"name": milestone.name, "icon_url": milestone.icon_url}
                           for _award, milestone in milestones],
            "events_attended": metrics["attendance_count"], "tasks_completed": metrics["task_count"],
            "contributions": metrics["contribution_count"], "service_activities": metrics["service_activities"],
            "leadership_activities": metrics["leadership_activities"],
            "engagement_dimensions": dimensions,
            "achievement_timeline": sorted(timeline, key=lambda item: item["occurred_at"])}


@router.patch("/me")
def update_my_profile(
    payload: ProfileUpdateInput,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user.profile, field, value)
    db.commit()
    return {"id": str(user.id), "username": user.profile.username,
            "display_name": user.profile.display_name, "visibility": user.profile.visibility.value,
            "bio": user.profile.bio, "location": user.profile.location, "photo_url": user.profile.photo_url}


@router.get("/{user_id}")
def public_profile(
    user_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    viewer: Annotated[User | None, Depends(get_optional_user)],
):
    user = db.get(User, user_id)
    if user is None or user.profile.visibility == ProfileVisibility.PRIVATE:
        raise HTTPException(status_code=404, detail="Profile not found")
    if viewer is not None and viewer.id == user.id:
        return {"username": user.profile.username, "display_name": user.profile.display_name,
                "bio": user.profile.bio, "photo_url": user.profile.photo_url}
    if user.profile.visibility == ProfileVisibility.MEMBERS:
        shared = db.scalar(select(Membership.id).where(
            Membership.user_id == viewer.id if viewer else False,
            Membership.community_id.in_(select(Membership.community_id).where(
                Membership.user_id == user_id, Membership.status == MembershipStatus.ACTIVE)),
            Membership.status == MembershipStatus.ACTIVE,
        ))
        if shared is None:
            raise HTTPException(status_code=404, detail="Profile not found")
    return {"username": user.profile.username, "display_name": user.profile.display_name,
            "bio": user.profile.bio, "photo_url": user.profile.photo_url}
