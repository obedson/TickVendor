"""Community and membership management API."""

import hashlib
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.authorization import require_community_role
from src.database import get_db
from src.models import (
    Community,
    CommunityLifecycleStatus,
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
from src.services.notification import audit, notify
from src.storage import cover_delivery_url

router = APIRouter(prefix="/communities", tags=["communities"])


class CommunityCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str | None = Field(default=None, max_length=5000)
    logo_url: str | None = Field(default=None, max_length=2048)
    is_public: bool = True
    membership_access: MembershipAccess = MembershipAccess.INVITE_ONLY
    organization_id: UUID | None = None
    initial_admin_user_id: UUID | None = None
    submit_for_review: bool = True


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
            "membership_access": data.membership_access.value,
            "organization_id": str(data.organization_id),
            "lifecycle_status": data.lifecycle_status.value,
            "submitted_by_id": str(data.submitted_by_id) if data.submitted_by_id else None,
            "reviewed_at": data.reviewed_at}


def _member_payload(membership, profile, viewer, email=None):
    """Shape one membership. `email` is supplied only on the Admin-gated governance surfaces."""
    visible = profile is not None and (profile.visibility != ProfileVisibility.PRIVATE or membership.user_id == viewer.id)
    data = {"id": str(membership.id), "user_id": str(membership.user_id), "role": membership.role.value,
            "status": membership.status.value}
    if visible:
        data.update({"username": profile.username, "display_name": profile.display_name,
                     "photo_url": profile.photo_url, "joined_at": membership.joined_at,
                     "created_at": membership.created_at})
    if email is not None:
        data["email"] = email
    return data


def _member(db, membership, viewer, email=None):
    profile = db.scalar(select(Profile).where(Profile.user_id == membership.user_id))
    return _member_payload(membership, profile, viewer, email)


def _managed_member(db, membership, viewer):
    """Response for the administrator-gated single-membership endpoints, which may show the email."""
    target = db.get(User, membership.user_id)
    return _member(db, membership, viewer, target.email if target else None)


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
             "online_url": event.online_url,
             "venue": {"name": event.venue.name, "address": event.venue.address, "city": event.venue.city, "region": event.venue.region, "lga": event.venue.lga, "country_code": event.venue.country_code, "latitude": event.venue.latitude, "longitude": event.venue.longitude} if event.venue else None}
            for event in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_community(payload: CommunityCreate, db: Annotated[Session, Depends(get_db)],
                     user: Annotated[User, Depends(get_current_user)]):
    if user.email_verified_at is None:
        raise HTTPException(403, "Verify your email before creating or applying for a community")
    values = payload.model_dump(exclude={"organization_id", "initial_admin_user_id", "submit_for_review"})
    organization = None
    initial_admin = user
    direct_creation = payload.organization_id is not None
    if direct_creation:
        organization = db.scalar(select(Organization).where(
            Organization.id == payload.organization_id,
            Organization.is_active.is_(True),
        ))
        if organization is None:
            raise HTTPException(404, "Organization not found")
        if user.role == PlatformRole.SUPER_ADMIN:
            if payload.initial_admin_user_id is None:
                raise HTTPException(422, "Select an initial Community Admin")
            initial_admin = governance.require_verified_admin_candidate(db.get(User, payload.initial_admin_user_id))
        else:
            authority_community_id = db.scalar(select(Community.id).join(Membership).where(
                Membership.user_id == user.id,
                Membership.role == MembershipRole.ADMIN,
                Membership.status == MembershipStatus.ACTIVE,
                Community.organization_id == organization.id,
                Community.is_active.is_(True),
                Community.deleted_at.is_(None),
            ))
            if authority_community_id is None:
                raise HTTPException(403, "Organization administrator authority required")
            # Serialize against role/suspension changes in the source community, then recheck
            # authority after acquiring the same community lock used by membership governance.
            governance.community_for_update(db, authority_community_id)
            authority = db.scalar(select(Membership.id).where(
                Membership.community_id == authority_community_id,
                Membership.user_id == user.id,
                Membership.role == MembershipRole.ADMIN,
                Membership.status == MembershipStatus.ACTIVE,
            ))
            if authority is None:
                raise HTTPException(403, "Organization administrator authority required")
            if payload.initial_admin_user_id not in {None, user.id}:
                raise HTTPException(403, "Only a Super Admin can select another initial administrator")
    else:
        organization = Organization(
            owner_id=user.id,
            name=payload.name,
            slug=f"{payload.slug}-org",
            is_active=False,
            is_verified=False,
        )
        db.add(organization)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="Community or organization slug already exists") from exc

    lifecycle_status = CommunityLifecycleStatus.ACTIVE
    if not direct_creation:
        lifecycle_status = (
            CommunityLifecycleStatus.PENDING_REVIEW
            if payload.submit_for_review
            else CommunityLifecycleStatus.DRAFT
        )
    community = Community(
        organization_id=organization.id,
        submitted_by_id=user.id,
        lifecycle_status=lifecycle_status,
        is_active=direct_creation,
        **values,
    )
    db.add(community)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Community slug already exists") from exc
    membership = Membership(
        community_id=community.id,
        user_id=initial_admin.id if direct_creation else user.id,
        role=MembershipRole.ADMIN,
        status=MembershipStatus.ACTIVE if direct_creation else MembershipStatus.PENDING,
    )
    db.add(membership)
    if direct_creation:
        governance.record_membership(
            db,
            membership,
            user,
            "admin_assigned",
            None,
            "Initial administrator for organization-scoped community creation",
        )
    action = "community.created" if direct_creation else (
        "community.application_submitted" if payload.submit_for_review else "community.draft_created"
    )
    audit(db, actor_id=user.id, community_id=community.id, action=action,
          target_type="community", target_id=community.id,
          metadata={"organization_id": str(organization.id), "lifecycle_status": community.lifecycle_status.value},
          commit=False)
    if not direct_creation and payload.submit_for_review:
        for super_admin_id in db.scalars(select(User.id).where(
            User.role == PlatformRole.SUPER_ADMIN,
            User.is_active.is_(True),
        )):
            notify(db, super_admin_id, "community_application_submitted", "Community application submitted",
                   f"{community.name} is ready for review.", {"community_id": str(community.id)},
                   community_id=community.id, commit=False)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="Community slug already exists") from exc
    return _community(community)


@router.post("/{community_id}/application/submit")
def submit_community_application(
    community_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    if user.email_verified_at is None:
        raise HTTPException(403, "Verify your email before submitting a community application")
    community = governance.community_for_update(db, community_id, active=False)
    if community.submitted_by_id != user.id:
        raise HTTPException(404, "Community application not found")
    if community.lifecycle_status == CommunityLifecycleStatus.PENDING_REVIEW:
        return _community(community)
    if community.lifecycle_status != CommunityLifecycleStatus.DRAFT:
        raise HTTPException(409, "Only draft community applications can be submitted")
    community.lifecycle_status = CommunityLifecycleStatus.PENDING_REVIEW
    audit(db, actor_id=user.id, community_id=community.id, action="community.application_submitted",
          target_type="community", target_id=community.id,
          metadata={"previous": {"lifecycle_status": "draft"},
                    "result": {"lifecycle_status": "pending_review"}}, commit=False)
    for super_admin_id in db.scalars(select(User.id).where(
        User.role == PlatformRole.SUPER_ADMIN,
        User.is_active.is_(True),
    )):
        notify(db, super_admin_id, "community_application_submitted", "Community application submitted",
               f"{community.name} is ready for review.", {"community_id": str(community.id)},
               community_id=community.id, commit=False)
    db.commit()
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
    """The community member directory, including contact details.

    This is governance data, so it stays with community Admins. Organizers resolve one member at
    a time through ``/members/search`` instead: the directory as a whole is a bulk export of
    personal information that operational event and task delivery never needs.
    """
    viewer = require_community_role(db, community_id, user, MembershipRole.ADMIN)
    rows = db.execute(select(Membership, Profile, User.email)
                      .join(User, User.id == Membership.user_id)
                      .outerjoin(Profile, Profile.user_id == Membership.user_id)
                      .where(Membership.community_id == community_id,
                             Membership.status != MembershipStatus.LEFT)
                      .order_by(Membership.created_at)).all()
    return {"members": [_member_payload(item, profile, viewer, email) for item, profile, email in rows]}


MEMBER_SEARCH_LIMIT = 10


def _like_pattern(term: str) -> str:
    """Escape LIKE wildcards so a query of ``%`` cannot be turned into a directory dump."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _search_kind(term: str) -> str:
    return "email" if "@" in term else "name"


@router.get("/{community_id}/members/search")
def search_members(
    community_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    q: Annotated[str, Query(min_length=2, max_length=320)],
):
    """Constrained operational member lookup for community Organizers.

    Deliberately not a directory: a real query is required, the result set is capped at
    ``MEMBER_SEARCH_LIMIT`` with no offset to page through, only active memberships are visible,
    and the response carries the minimum needed to identify somebody operationally. An email is
    disclosed only when the query *was* that exact address, so a name or username search never
    becomes a way to harvest addresses. A user outside this community is indistinguishable from
    a user who does not exist, so cross-community membership cannot be probed.
    """
    viewer = require_community_role(db, community_id, user, MembershipRole.ORGANIZER)
    term = q.strip()
    if len(term) < 2:
        raise HTTPException(status_code=422, detail="Enter at least two characters to search")
    lowered = term.lower()
    exact_email = lowered if "@" in lowered else None
    username = lowered.lstrip("@")
    rows = db.execute(
        select(Membership, Profile, User)
        .join(User, User.id == Membership.user_id)
        .outerjoin(Profile, Profile.user_id == Membership.user_id)
        .where(
            Membership.community_id == community_id,
            Membership.status == MembershipStatus.ACTIVE,
            User.is_active.is_(True),
            or_(
                User.email == exact_email,
                func.lower(Profile.username) == username,
                func.lower(Profile.username).like(_like_pattern(username), escape="\\"),
                func.lower(Profile.display_name).like(_like_pattern(lowered), escape="\\"),
            ),
        )
        .order_by(Profile.display_name, User.id)
        .limit(MEMBER_SEARCH_LIMIT)
    ).all()
    members = []
    for membership, profile, target in rows:
        visible = profile is not None and (
            profile.visibility != ProfileVisibility.PRIVATE or membership.user_id == viewer.user_id
        )
        item = {
            "user_id": str(membership.user_id),
            "membership_id": str(membership.id),
            "display_name": profile.display_name if visible else "Private member",
            "username": profile.username if visible else None,
            "role": membership.role.value,
            "status": membership.status.value,
        }
        # Only an exact-email lookup may echo the address back; a name match must not.
        if exact_email is not None and target.email.lower() == exact_email:
            item["email"] = target.email
        members.append(item)
    # Recorded as a digest, never the raw term, so the audit trail cannot itself become a store
    # of members' email addresses.
    audit(db, actor_id=viewer.user_id, community_id=community_id, action="community.member_searched",
          target_type="community", target_id=community_id,
          metadata={"query_kind": _search_kind(term), "query_digest": hashlib.sha256(lowered.encode()).hexdigest()[:16],
                    "result_count": len(members)})
    return {"members": members}


@router.post("/{community_id}/members", status_code=status.HTTP_201_CREATED)
def add_member(community_id: UUID, payload: MemberAdd, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    membership = governance.invite(db, community_id, user, payload.user_id, payload.role)
    return _managed_member(db, membership, user)


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
    return _managed_member(db, membership, user)


@router.patch("/{community_id}/members/{membership_id}/role")
def change_role(community_id: UUID, membership_id: UUID, payload: MemberRole, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    membership = governance.manage_membership(db, community_id, membership_id, user, "role_changed", payload.reason, payload.role)
    return _managed_member(db, membership, user)


@router.patch("/{community_id}/members/{membership_id}/status")
def change_status(community_id: UUID, membership_id: UUID, payload: MemberStatus, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    action = {MembershipStatus.ACTIVE: "activated", MembershipStatus.SUSPENDED: "deactivated"}.get(payload.status)
    if action is None:
        raise HTTPException(422, "Use the explicit invitation/join/leave lifecycle")
    membership = governance.manage_membership(db, community_id, membership_id, user, action, payload.reason)
    return _managed_member(db, membership, user)


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
    return _managed_member(db, governance.manage_membership(db, community_id, membership_id, user, action, payload.reason), user)
