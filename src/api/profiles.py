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
    Event,
    EventStatus,
    ImpactTransaction,
    ImpactTransactionStatus,
    ProfileVisibility,
    User,
)

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
def my_profile(db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    points = db.scalar(select(func.coalesce(func.sum(ImpactTransaction.points), 0)).where(
        ImpactTransaction.user_id == user.id, ImpactTransaction.status == ImpactTransactionStatus.POSTED
    ))
    return {"id": str(user.id), "username": user.profile.username,
            "display_name": user.profile.display_name, "visibility": user.profile.visibility.value,
            "impact_points": points}


@router.get("/{user_id}")
def public_profile(user_id: UUID, db: Annotated[Session, Depends(get_db)]):
    user = db.get(User, user_id)
    if user is None or user.profile.visibility == ProfileVisibility.PRIVATE:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"username": user.profile.username, "display_name": user.profile.display_name,
            "bio": user.profile.bio, "photo_url": user.profile.photo_url}
