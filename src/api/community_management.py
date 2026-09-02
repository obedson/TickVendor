"""Community and membership management API."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.authorization import require_community_role
from src.database import get_db
from src.models import (
    Community,
    Membership,
    MembershipRole,
    MembershipStatus,
    Organization,
    PlatformRole,
    Profile,
    ProfileVisibility,
    User,
)
from src.services.notification import audit

router = APIRouter(prefix="/communities", tags=["communities"])


class CommunityCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str | None = Field(default=None, max_length=5000)
    logo_url: str | None = Field(default=None, max_length=2048)
    is_public: bool = True


class CommunityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    logo_url: str | None = Field(default=None, max_length=2048)
    is_public: bool | None = None
    is_active: bool | None = None


class MemberAdd(BaseModel):
    user_id: UUID
    role: MembershipRole = MembershipRole.MEMBER


class MemberRole(BaseModel):
    role: MembershipRole


class MemberStatus(BaseModel):
    status: MembershipStatus


def _community(data):
    return {"id": str(data.id), "name": data.name, "slug": data.slug, "description": data.description,
            "logo_url": data.logo_url, "is_public": data.is_public, "is_active": data.is_active}


def _member(db, membership, viewer):
    profile = db.get(Profile, membership.user_id)
    if profile is None or profile.visibility == ProfileVisibility.PRIVATE and membership.user_id != viewer.id:
        return {"id": str(membership.id), "user_id": str(membership.user_id), "role": membership.role.value,
                "status": membership.status.value}
    return {"id": str(membership.id), "user_id": str(membership.user_id), "role": membership.role.value,
            "status": membership.status.value, "username": profile.username, "display_name": profile.display_name,
            "photo_url": profile.photo_url}


@router.get("/me", include_in_schema=True)
def my_communities(db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    memberships = db.scalars(select(Membership).where(
        Membership.user_id == user.id, Membership.status == MembershipStatus.ACTIVE,
    ).order_by(Membership.created_at)).all()
    return [{"id": str(item.community_id), "community": _community(db.get(Community, item.community_id)),
             "membership": {"id": str(item.id), "role": item.role.value, "status": item.status.value}}
            for item in memberships]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_community(payload: CommunityCreate, db: Annotated[Session, Depends(get_db)],
                     user: Annotated[User, Depends(get_current_user)]):
    organization = Organization(owner_id=user.id, name=payload.name, slug=f"{payload.slug}-org")
    db.add(organization); db.flush()
    community = Community(organization_id=organization.id, **payload.model_dump())
    db.add(community); db.flush()
    db.add(Membership(community_id=community.id, user_id=user.id, role=MembershipRole.ADMIN, status=MembershipStatus.ACTIVE))
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
    if "is_active" in values and user.role != PlatformRole.SUPER_ADMIN:
        values.pop("is_active")
    for field, value in values.items(): setattr(community, field, value)
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
    require_community_role(db, community_id, user, MembershipRole.ADMIN)
    if payload.user_id == user.id or payload.role == MembershipRole.ADMIN and user.role != PlatformRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Cannot assign that membership role")
    if db.get(User, payload.user_id) is None: raise HTTPException(status_code=404, detail="User not found")
    membership = db.scalar(select(Membership).where(Membership.community_id == community_id, Membership.user_id == payload.user_id))
    if membership is not None and membership.status != MembershipStatus.LEFT:
        raise HTTPException(status_code=409, detail="Membership already exists")
    if membership is None: membership = Membership(community_id=community_id, user_id=payload.user_id)
    membership.role = payload.role; membership.status = MembershipStatus.INVITED
    db.add(membership)
    audit(db, actor_id=user.id, community_id=community_id, action="membership.invited", target_type="membership", target_id=membership.id, metadata={"user_id": str(payload.user_id)}, commit=False)
    db.commit()
    return _member(db, membership, user)


@router.patch("/{community_id}/members/{membership_id}/role")
def change_role(community_id: UUID, membership_id: UUID, payload: MemberRole, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    require_community_role(db, community_id, user, MembershipRole.ADMIN)
    membership = db.get(Membership, membership_id)
    if membership is None or membership.community_id != community_id: raise HTTPException(status_code=404, detail="Membership not found")
    if membership.user_id == user.id or payload.role == MembershipRole.ADMIN and user.role != PlatformRole.SUPER_ADMIN: raise HTTPException(status_code=403, detail="Role change forbidden")
    previous = membership.role; membership.role = payload.role
    audit(db, actor_id=user.id, community_id=community_id, action="membership.role_changed", target_type="membership", target_id=membership.id, metadata={"from": previous.value, "to": payload.role.value}, commit=False)
    db.commit(); return _member(db, membership, user)


@router.patch("/{community_id}/members/{membership_id}/status")
def change_status(community_id: UUID, membership_id: UUID, payload: MemberStatus, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    require_community_role(db, community_id, user, MembershipRole.ADMIN)
    membership = db.get(Membership, membership_id)
    if membership is None or membership.community_id != community_id: raise HTTPException(status_code=404, detail="Membership not found")
    if membership.user_id == user.id and payload.status != MembershipStatus.ACTIVE: raise HTTPException(status_code=403, detail="Cannot deactivate own membership")
    membership.status = payload.status
    audit(db, actor_id=user.id, community_id=community_id, action="membership.status_changed", target_type="membership", target_id=membership.id, metadata={"status": payload.status.value}, commit=False)
    db.commit(); return _member(db, membership, user)
