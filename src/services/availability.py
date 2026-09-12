"""Platform suspension gates, separate from business lifecycle statuses."""
from fastapi import HTTPException
from sqlalchemy import select

from src.models import Community


def visible_content(model):
    return (~model.is_suspended) & model.community_id.in_(select(Community.id).where(
        Community.is_active.is_(True), Community.deleted_at.is_(None)))


def require_available(db, item):
    if item is None or getattr(item, "deleted_at", None) is not None:
        raise HTTPException(404, "Content not found")
    community = db.get(Community, item.community_id)
    if item.is_suspended or community is None or not community.is_active or community.deleted_at is not None:
        raise HTTPException(403, "This content or community is suspended")
    return item
