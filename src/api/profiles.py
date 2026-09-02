"""Authenticated profile and journey summary API."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
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
    User,
)
from src.services.recognition import current_rank, next_rank, user_metrics

router = APIRouter(prefix="/profiles", tags=["profiles"])


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
        return {"id": str(user.id), "username": user.profile.username,
                "display_name": user.profile.display_name, "visibility": user.profile.visibility.value,
                "impact_points": points}
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


@router.get("/{user_id}")
def public_profile(user_id: UUID, db: Annotated[Session, Depends(get_db)]):
    user = db.get(User, user_id)
    if user is None or user.profile.visibility == ProfileVisibility.PRIVATE:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"username": user.profile.username, "display_name": user.profile.display_name,
            "bio": user.profile.bio, "photo_url": user.profile.photo_url}
