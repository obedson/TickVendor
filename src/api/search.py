"""Privacy-aware global search API."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.database import get_db
from src.models import (
    Community,
    Event,
    EventStatus,
    Membership,
    MembershipRole,
    MembershipStatus,
    Profile,
    ProfileVisibility,
    Task,
    User,
)

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def global_search(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    q: str = Query(min_length=2, max_length=100),
):
    pattern = f"%{q.lower()}%"
    events = db.scalars(select(Event).where(
        Event.status == EventStatus.PUBLISHED, func.lower(Event.title).like(pattern)
    ).limit(20))
    communities = db.scalars(select(Community).where(
        Community.is_public.is_(True), func.lower(Community.name).like(pattern)
    ).limit(20))
    public_profiles = list(db.scalars(select(Profile).where(
        Profile.visibility == ProfileVisibility.PUBLIC,
        (func.lower(Profile.username).like(pattern) | func.lower(Profile.display_name).like(pattern)),
    ).limit(20)))
    member_profiles = list(db.scalars(
        select(Profile).join(Membership, Membership.user_id == Profile.user_id).where(
            Profile.visibility == ProfileVisibility.MEMBERS,
            Membership.status == MembershipStatus.ACTIVE,
            Membership.community_id.in_(select(Membership.community_id).where(
                Membership.user_id == user.id, Membership.status == MembershipStatus.ACTIVE,
            )),
            (func.lower(Profile.username).like(pattern) | func.lower(Profile.display_name).like(pattern)),
        ).limit(20)
    ))
    profiles = {profile.user_id: profile for profile in public_profiles + member_profiles}.values()
    organizers = db.execute(
        select(Profile, Membership.community_id)
        .join(Membership, Membership.user_id == Profile.user_id)
        .where(
            Membership.role.in_([MembershipRole.ORGANIZER, MembershipRole.ADMIN]),
            Membership.status == MembershipStatus.ACTIVE,
            Profile.visibility != ProfileVisibility.PRIVATE,
            (func.lower(Profile.username).like(pattern) | func.lower(Profile.display_name).like(pattern)),
        )
        .limit(20)
    )
    tasks = db.scalars(
        select(Task)
        .join(Membership, Membership.community_id == Task.community_id)
        .where(
            Membership.user_id == user.id,
            Membership.status == MembershipStatus.ACTIVE,
            Task.is_active.is_(True),
            func.lower(Task.title).like(pattern),
        )
        .limit(20)
    )
    return {
        "events": [{"id": str(item.id), "title": item.title} for item in events],
        "communities": [{"id": str(item.id), "name": item.name} for item in communities],
        "members": [{"username": item.username, "display_name": item.display_name} for item in profiles],
        "organizers": [
            {"username": profile.username, "display_name": profile.display_name,
             "community_id": str(community_id)}
            for profile, community_id in organizers
        ],
        "tasks": [
            {"id": str(item.id), "title": item.title, "community_id": str(item.community_id)}
            for item in tasks
        ],
    }
