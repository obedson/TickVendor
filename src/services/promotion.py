"""Placements never grant access, and recheck eligibility on every delivery."""
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select

from src.models import (
    ActivityOpportunity,
    Community,
    Event,
    EventStatus,
    Membership,
    MembershipStatus,
    PlatformRole,
    Task,
)
from src.models.opportunity import OpportunityStatus
from src.models.promotion import Promotion
from src.services.notification import audit
from src.storage import cover_delivery_url

CONTENT = {"community": Community, "event": Event, "opportunity": ActivityOpportunity, "task": Task}


def admin(user):
    if user.role != PlatformRole.SUPER_ADMIN:
        raise HTTPException(403, "Super Admin authority required")


def eligible_query(kind, now):
    model = CONTENT[kind]
    query = select(model)
    if kind != "task":
        query = query.where(model.deleted_at.is_(None))
    if kind == "community":
        return query.where(Community.is_public.is_(True), Community.is_active.is_(True))
    query = query.where(model.is_suspended.is_(False), model.community_id.in_(select(Community.id).where(
        Community.is_active.is_(True), Community.is_public.is_(True), Community.deleted_at.is_(None))))
    if kind == "event":
        return query.where(Event.status == EventStatus.PUBLISHED, Event.ends_at > now)
    if kind == "opportunity":
        return query.where(ActivityOpportunity.status == OpportunityStatus.PUBLISHED, ActivityOpportunity.ends_at > now, ActivityOpportunity.members_only.is_(False))
    return query.where(Task.is_active.is_(True), (Task.due_at.is_(None) | (Task.due_at > now)))


def serialize_content(kind, item):
    image = cover_delivery_url(item.cover_image_url, item.community_id, item.id) if kind == "event" else item.logo_url if kind == "community" else None
    return {"content_id": str(item.id), "content_type": kind, "headline": item.name if kind == "community" else item.title,
            "body": (item.description or "")[:1000], "imageUrl": image}


def save(db, actor, payload, promotion_id=None):
    admin(actor)
    values = payload.model_dump(exclude={"reason"})
    if db.scalar(eligible_query(payload.content_type, datetime.now(UTC)).where(CONTENT[payload.content_type].id == payload.content_id)) is None:
        raise HTTPException(422, "Choose eligible, active public-community content. Tasks are delivered only to active members.")
    item = db.get(Promotion, promotion_id) if promotion_id else Promotion(created_by_id=actor.id)
    if item is None:
        raise HTTPException(404, "Promotion not found")
    for key, value in values.items():
        setattr(item, key, value)
    db.add(item); db.flush()
    audit(db, actor_id=actor.id, action="promotion.updated" if promotion_id else "promotion.created", target_type="promotion", target_id=item.id,
          metadata={"reason": payload.reason, "content_type": item.content_type, "content_id": str(item.content_id), "classification": item.classification, "surface": item.surface, "is_active": item.is_active}, commit=False)
    db.commit()
    return item


def deliver(db, surface, user=None):
    now = datetime.now(UTC)
    # Four set-based content lookups, not one query per placement.
    rows = list(db.scalars(select(Promotion).where(Promotion.surface == surface, Promotion.is_active.is_(True), Promotion.starts_at <= now, Promotion.ends_at > now)
                          .order_by(Promotion.priority.desc(), Promotion.id).limit(100)))
    # One delivery per underlying item: conflicting placements must not repeat the same content.
    placements, seen = [], set()
    for row in rows:
        key = (row.content_type, row.content_id)
        if key not in seen:
            seen.add(key)
            placements.append(row)
    contents = {}
    for kind, model in CONTENT.items():
        ids = [row.content_id for row in placements if row.content_type == kind]
        if not ids or kind == "task" and user is None:
            continue
        query = eligible_query(kind, now).where(model.id.in_(ids))
        if kind == "task":
            query = query.where(Task.community_id.in_(select(Membership.community_id).where(Membership.user_id == user.id, Membership.status == MembershipStatus.ACTIVE)))
        contents.update({(kind, item.id): item for item in db.scalars(query)})
    return [{"id": str(row.id), "classification": row.classification, **serialize_content(row.content_type, contents[(row.content_type, row.content_id)])}
            for row in placements if (row.content_type, row.content_id) in contents][:12]
