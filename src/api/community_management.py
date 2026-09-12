"""Community and membership management API."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.authorization import require_community_role
from src.database import get_db
from src.models import (
    Community,
    Event,
    Membership,
    MembershipAccess,
    MembershipRole,
    MembershipStatus,
    Organization,
    PlatformRole,
    Profile,
    ProfileVisibility,
    User,
)
from src.services import governance
from src.services.notification import audit
from src.storage import cover_delivery_url

router = APIRouter(prefix="/communities", tags=["communities"])


class CommunityCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str | None = Field(default=None, max_length=5000)
    logo_url: str | None = Field(default=None, max_length=2048)
    is_public: bool = True
    membership_access: MembershipAccess = MembershipAccess.INVITE_ONLY


class CommunityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    logo_url: str | None = Field(default=None, max_length=2048)
    is_public: bool | None = None
    membership_access: MembershipAccess | None = None


class MemberAdd(BaseModel):
    user_id: UUID
    role: MembershipRole = MembershipRole.MEMBER


class MemberInviteByIdentifier(BaseModel):
    """Invite a member by email or username (organizer-friendly)."""
    identifier: str = Field(min_length=1, max_length=255, description="Email address or username")
    role: MembershipRole = MembershipRole.MEMBER


class MemberRole(BaseModel):
    role: MembershipRole
    reason: str = Field(min_length=3, max_length=1000)


class MemberStatus(BaseModel):
    status: MembershipStatus
    reason: str = Field(min_length=3, max_length=1000)


def _community(data):
    return {"id": str(data.id), "name": data.name, "slug": data.slug, "description": data.description,
            "logo_url": data.logo_url, "is_public": data.is_public, "is_active": data.is_active,
            "membership_access": data.membership_access.value}


def _member(db, membership, viewer):
    profile = db.scalar(select(Profile).where(Profile.user_id == membership.user_id))
    if profile is None or profile.visibility == ProfileVisibility.PRIVATE and membership.user_id != viewer.id:
        return {"id": str(membership.id), "user_id": str(membership.user_id), "role": membership.role.value,
                "status": membership.status.value}
    return {"id": str(membership.id), "user_id": str(membership.user_id), "role": membership.role.value,
            "status": membership.status.value, "username": profile.username, "display_name": profile.display_name,
            "photo_url": profile.photo_url, "joined_at": membership.joined_at, "created_at": membership.created_at}


@router.get("/me", include_in_schema=True)
def my_communities(db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    memberships = db.scalars(select(Membership).where(
        Membership.user_id == user.id,
    ).order_by(Membership.created_at)).all()
    return [{"id": str(item.community_id), "community": _community(db.get(Community, item.community_id)),
             "membership": {"id": str(item.id), "role": item.role.value, "status": item.status.value, "created_at": item.created_at}}
            for item in memberships]


@router.get("/organizer/events")
def organizer_events(db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    rows = db.scalars(select(Event).where(
        Event.organizer_id == user.id, Event.deleted_at.is_(None),
    ).order_by(Event.starts_at, Event.created_at)).all()
    return [{"id": str(event.id), "community_id": str(event.community_id), "title": event.title, "description": event.description,
             "status": event.status.value, "starts_at": event.starts_at, "ends_at": event.ends_at,
             "category": event.category,
             "cover_image_url": cover_delivery_url(event.cover_image_url, event.community_id, event.id),
             "venue": {"name": event.venue.name, "city": event.venue.city} if event.venue else None}
            for event in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_community(payload: CommunityCreate, db: Annotated[Session, Depends(get_db)],
                     user: Annotated[User, Depends(get_current_user)]):
    if user.role != PlatformRole.SUPER_ADMIN and db.scalar(select(Membership.id).join(Community).where(
        Membership.user_id == user.id, Membership.role == MembershipRole.ADMIN,
        Membership.status == MembershipStatus.ACTIVE, Community.is_active.is_(True),
    )) is None:
        raise HTTPException(403, "Community administrator authority required to create a community")
    organization = Organization(owner_id=user.id, name=payload.name, slug=f"{payload.slug}-org")
    db.add(organization); db.flush()
    community = Community(organization_id=organization.id, **payload.model_dump())
    db.add(community); db.flush()
    db.add(Membership(community_id=community.id, user_id=user.id, role=MembershipRole.ORGANIZER, status=MembershipStatus.ACTIVE))
    audit(db, actor_id=user.id, community_id=community.id, action="community.created", target_type="community", target_id=community.id, commit=False)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="Community slug already exists") from exc
    return _community(community)


@router.patch("/{community_id}")
def update_community(community_id: UUID, payload: CommunityUpdate, db: Annotated[Session, Depends(get_db)],
                     user: Annotated[User, Depends(get_current_user)]):
    require_community_role(db, community_id, user, MembershipRole.ADMIN)
    community = db.get(Community, community_id)
    if community is None: raise HTTPException(status_code=404, detail="Community not found")
    values = payload.model_dump(exclude_unset=True)
    for field, value in values.items():
        if value is None and field not in {"description", "logo_url"}:
            raise HTTPException(422, "Community settings cannot be null")
        setattr(community, field, value)
    audit(db, actor_id=user.id, community_id=community_id, action="community.updated", target_type="community", target_id=community_id, metadata={"fields": sorted(values)}, commit=False)
    db.commit()
    return _community(community)


@router.get("/{community_id}/members")
def list_members(community_id: UUID, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    require_community_role(db, community_id, user)
    memberships = db.scalars(select(Membership).where(Membership.community_id == community_id,
                                                       Membership.status != MembershipStatus.LEFT).order_by(Membership.created_at)).all()
    return {"members": [_member(db, item, user) for item in memberships]}


@router.post("/{community_id}/members", status_code=status.HTTP_201_CREATED)
def add_member(community_id: UUID, payload: MemberAdd, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    membership = governance.invite(db, community_id, user, payload.user_id, payload.role)
    return _member(db, membership, user)


@router.post("/{community_id}/members/invite", status_code=status.HTTP_201_CREATED)
def invite_member_by_identifier(
    community_id: UUID,
    payload: MemberInviteByIdentifier,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Invite a member by email address or username.

    Looks up the user by email (exact match) or username (exact match, case-insensitive).
    Respects profile privacy: does not expose whether an email exists to unauthorized callers
    (returns 404 for both not-found and privacy-redacted cases).
    """
    require_community_role(db, community_id, user, MembershipRole.ADMIN)
    identifier = payload.identifier.strip()
    # Try email first, then username.
    target_user: User | None = None
    if "@" in identifier:
        target_user = db.scalar(select(User).where(User.email == identifier.lower()))
    if target_user is None:
        # Username lookup via Profile.
        profile = db.scalar(
            select(Profile).where(Profile.username == identifier.lower().lstrip("@"))
        )
        if profile:
            target_user = db.get(User, profile.user_id)
    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    membership = governance.invite(db, community_id, user, target_user.id, payload.role)
    return _member(db, membership, user)


@router.patch("/{community_id}/members/{membership_id}/role")
def change_role(community_id: UUID, membership_id: UUID, payload: MemberRole, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    membership = governance.manage_membership(db, community_id, membership_id, user, "role_changed", payload.reason, payload.role)
    return _member(db, membership, user)


@router.patch("/{community_id}/members/{membership_id}/status")
def change_status(community_id: UUID, membership_id: UUID, payload: MemberStatus, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    action = {MembershipStatus.ACTIVE: "activated", MembershipStatus.SUSPENDED: "deactivated"}.get(payload.status)
    if action is None:
        raise HTTPException(422, "Use the explicit invitation/join/leave lifecycle")
    membership = governance.manage_membership(db, community_id, membership_id, user, action, payload.reason)
    return _member(db, membership, user)


class MembershipAction(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


@router.get("/discover")
def discover_communities(db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)],
                         q: str = "", offset: int = 0):
    from sqlalchemy import func
    rows = db.scalars(select(Community).where(Community.is_public.is_(True), Community.is_active.is_(True),
        Community.deleted_at.is_(None), func.lower(Community.name).contains(q.lower()[:100]))
        .order_by(Community.name, Community.id).offset(max(0, offset)).limit(50))
    return [{**_community(item), "membership": state if (state := governance.state(governance.member_for(db, item.id, user.id))) else None}
            for item in rows]


@router.post("/{community_id}/membership/{action}")
def participant_membership(community_id: UUID, action: str, db: Annotated[Session, Depends(get_db)],
                           user: Annotated[User, Depends(get_current_user)]):
    item = governance.participant_transition(db, community_id, user, action)
    return {"id": str(item.id), **governance.state(item)}


@router.post("/{community_id}/membership-requests/{membership_id}/{action}")
def review_membership(community_id: UUID, membership_id: UUID, action: str, payload: MembershipAction,
                      db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    if action not in {"approved", "rejected"}:
        raise HTTPException(422, "Choose approved or rejected")
    return _member(db, governance.manage_membership(db, community_id, membership_id, user, action, payload.reason), user)
