"""Privacy-aware global search API."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.database import get_db
from src.models import Community, Event, EventStatus, Profile, ProfileVisibility, User

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def global_search(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    q: str = Query(min_length=2, max_length=100),
):
    pattern = f"%{q.lower()}%"
    events = db.scalars(select(Event).where(
        Event.status == EventStatus.PUBLISHED, func.lower(Event.title).like(pattern)
    ).limit(20))
    communities = db.scalars(select(Community).where(
        Community.is_public.is_(True), func.lower(Community.name).like(pattern)
    ).limit(20))
    profiles = db.scalars(select(Profile).where(
        Profile.visibility != ProfileVisibility.PRIVATE,
        (func.lower(Profile.username).like(pattern) | func.lower(Profile.display_name).like(pattern)),
    ).limit(20))
    return {
        "events": [{"id": str(item.id), "title": item.title} for item in events],
        "communities": [{"id": str(item.id), "name": item.name} for item in communities],
        "members": [{"username": item.username, "display_name": item.display_name} for item in profiles],
    }
