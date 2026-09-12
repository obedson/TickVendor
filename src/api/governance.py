"""Super Admin directory, reversible moderation and governance history."""
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from src.authorization import require_platform_roles
from src.database import get_db
from src.models import (
    AuditLog,
    Community,
    Membership,
    MembershipRole,
    MembershipStatus,
    PlatformRole,
    Profile,
    User,
)
from src.services.governance import MODERATION_MODELS, assign_admin, manage_membership, moderate

router = APIRouter(prefix="/admin/platform/governance", tags=["platform governance"])
DB = Annotated[Session, Depends(get_db)]
Admin = Annotated[User, Depends(require_platform_roles(PlatformRole.SUPER_ADMIN))]
Kind = Literal["user", "community", "event", "opportunity", "task"]


class Reason(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator("reason")
    @classmethod
    def meaningful(cls, value):
        if len(value.strip()) < 3:
            raise ValueError("A meaningful reason is required")
        return value.strip()


class ModerationInput(Reason):
    suspended: bool


class AdminAssignment(Reason):
    user_id: UUID


class MembershipChange(Reason):
    action: Literal["role_changed", "activated", "deactivated"]
    role: MembershipRole | None = None


def identity(db, user_id):
    user = db.get(User, user_id)
    profile = user.profile if user else None
    return {"id": str(user_id), "name": profile.display_name if profile else user.email if user else "Former user",
            "username": profile.username if profile else None, "email": user.email if user else None}


def target_name(db, kind, target_id):
    if kind == "membership":
        item = db.get(Membership, target_id)
        return identity(db, item.user_id)["name"] if item else "Former membership"
    model = MODERATION_MODELS.get(kind)
    item = db.get(model, target_id) if model else None
    if kind == "user":
        return identity(db, target_id)["name"]
    return (getattr(item, "title", None) or getattr(item, "name", None)) if item else "Former record"


def summary(db, kind, item):
    result = {"id": str(item.id), "name": getattr(item, "title", None) or getattr(item, "name", None),
              "suspended": not item.is_active if kind in {"user", "community"} else item.is_suspended,
              "created_at": item.created_at}
    if kind == "user":
        result.update(identity(db, item.id), role=item.role.value, is_active=item.is_active,
                      is_email_verified=item.email_verified_at is not None)
    if kind == "community":
        result.update(is_public=item.is_public, is_active=item.is_active, membership_access=item.membership_access.value,
                      member_count=db.scalar(select(func.count(Membership.id)).where(Membership.community_id == item.id,
                          Membership.status == MembershipStatus.ACTIVE)))
    if kind in {"event", "opportunity", "task"}:
        community = db.get(Community, item.community_id)
        result.update(community_id=str(item.community_id), community_name=community.name if community else "Former community",
                      owner=identity(db, item.organizer_id if kind == "event" else item.created_by_id),
                      status=item.status.value if hasattr(item, "status") else "active" if item.is_active else "inactive",
                      description=item.description, starts_at=getattr(item, "starts_at", None))
    return result


@router.get("/history")
def history(db: DB, user: Admin, target_id: UUID | None = None, offset: int = Query(0, ge=0)):
    query = select(AuditLog).where(or_(AuditLog.action.like("moderation.%"), AuditLog.action.like("membership.%")))
    if target_id:
        query = query.where(or_(AuditLog.target_id == target_id, AuditLog.community_id == target_id,
            AuditLog.target_id.in_(select(Membership.id).where(Membership.user_id == target_id))))
    rows = db.scalars(query.order_by(AuditLog.occurred_at.desc(), AuditLog.id).offset(offset).limit(50))
    return [{"id": str(item.id), "actor": identity(db, item.actor_id)["name"] if item.actor_id else "System",
             "action": item.action.replace('.', ' ').replace('_', ' '), "target_type": item.target_type,
             "target_name": target_name(db, item.target_type, item.target_id),
             "target_id": str(item.target_id), "community": db.get(Community, item.community_id).name if item.community_id and db.get(Community, item.community_id) else None,
             "reason": item.metadata_json.get("reason", ""), "previous": item.metadata_json.get("previous"),
             "result": item.metadata_json.get("result"), "occurred_at": item.occurred_at} for item in rows]


@router.get("/{kind}")
def directory(kind: Kind, db: DB, user: Admin, q: str = Query("", max_length=100),
              community_id: UUID | None = None, creator_id: UUID | None = None,
              status: str | None = None, suspended: bool | None = None,
              after: datetime | None = None, before: datetime | None = None,
              offset: int = Query(0, ge=0)):
    model = MODERATION_MODELS[kind]
    query = select(model)
    if kind == "user":
        query = query.outerjoin(Profile, Profile.user_id == User.id).where(or_(
            func.lower(User.email).contains(q.lower()), func.lower(Profile.username).contains(q.lower()),
            func.lower(Profile.display_name).contains(q.lower())))
    else:
        column = model.name if kind == "community" else model.title
        query = query.where(func.lower(column).contains(q.lower()))
    if suspended is not None:
        query = query.where(model.is_active.is_(not suspended) if kind in {"user", "community"} else model.is_suspended.is_(suspended))
    if kind in {"event", "opportunity", "task"}:
        if community_id:
            query = query.where(model.community_id == community_id)
        if creator_id:
            query = query.where((model.organizer_id if kind == "event" else model.created_by_id) == creator_id)
        if status:
            if kind == "task":
                query = query.where(model.is_active.is_(status == "active"))
            else:
                enum = model.status.type.enum_class
                try:
                    query = query.where(model.status == enum(status))
                except ValueError as exc:
                    raise HTTPException(422, "Invalid content status") from exc
    if after:
        query = query.where(model.created_at >= after)
    if before:
        query = query.where(model.created_at <= before)
    return [summary(db, kind, item) for item in db.scalars(query.order_by(model.created_at.desc(), model.id).offset(offset).limit(50))]


@router.get("/{kind}/{target_id}")
def inspect_target(kind: Kind, target_id: UUID, db: DB, user: Admin, membership_offset: int = Query(0, ge=0)):
    item = db.get(MODERATION_MODELS[kind], target_id)
    if item is None:
        raise HTTPException(404, "Target not found")
    result = summary(db, kind, item)
    if kind in {"user", "community"}:
        query = select(Membership).where(Membership.user_id == target_id if kind == "user" else Membership.community_id == target_id)
        rows = list(db.scalars(query.order_by(case((Membership.role == MembershipRole.ADMIN, 0), else_=1),
                                             Membership.created_at, Membership.id).offset(membership_offset).limit(51)))
        result["membership_offset"] = membership_offset
        result["memberships_has_more"] = len(rows) > 50
        result["active_admin_count"] = db.scalar(select(func.count(Membership.id)).where(
            Membership.community_id == target_id, Membership.role == MembershipRole.ADMIN,
            Membership.status == MembershipStatus.ACTIVE)) if kind == "community" else None
        result["memberships"] = [{"id": str(m.id), **identity(db, m.user_id), "membership_id": str(m.id),
            "community_id": str(m.community_id), "community_name": db.get(Community, m.community_id).name,
            "role": m.role.value, "status": m.status.value} for m in rows[:50]]
    return result


@router.post("/{kind}/{target_id}/moderation")
def moderation(kind: Kind, target_id: UUID, payload: ModerationInput, db: DB, user: Admin):
    return summary(db, kind, moderate(db, user, kind, target_id, payload.suspended, payload.reason))


@router.post("/community/{community_id}/administrators")
def administrator(community_id: UUID, payload: AdminAssignment, db: DB, user: Admin):
    item = assign_admin(db, community_id, payload.user_id, user, payload.reason)
    return {"id": str(item.id), "role": item.role.value, "status": item.status.value}


@router.patch("/community/{community_id}/memberships/{membership_id}")
def membership(community_id: UUID, membership_id: UUID, payload: MembershipChange, db: DB, user: Admin):
    if payload.action == "role_changed" and payload.role is None:
        raise HTTPException(422, "Role is required")
    item = manage_membership(db, community_id, membership_id, user, payload.action, payload.reason, payload.role)
    return {"id": str(item.id), "role": item.role.value, "status": item.status.value}
