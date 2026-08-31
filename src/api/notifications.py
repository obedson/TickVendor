"""In-app notification API."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.database import get_db
from src.models import Notification, NotificationPreference, User
from src.schemas.notification import NotificationPreferenceUpdate

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/preferences")
def get_preferences(
    db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)],
):
    preference = db.query(NotificationPreference).filter_by(user_id=user.id).one_or_none()
    if preference is None:
        preference = NotificationPreference(user_id=user.id)
        db.add(preference)
        db.commit()
    return {"in_app_enabled": preference.in_app_enabled, "email_enabled": preference.email_enabled,
            "push_enabled": preference.push_enabled, "muted_types": preference.muted_types}


@router.put("/preferences")
def update_preferences(
    payload: NotificationPreferenceUpdate,
    db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)],
):
    preference = db.query(NotificationPreference).filter_by(user_id=user.id).one_or_none()
    if preference is None:
        preference = NotificationPreference(user_id=user.id)
        db.add(preference)
    for field in ("in_app_enabled", "email_enabled", "push_enabled", "muted_types"):
        value = getattr(payload, field)
        if value is not None:
            setattr(preference, field, value)
    db.commit()
    return {"status": "updated"}


@router.get("")
def list_notifications(
    db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)],
    unread_only: bool = False,
):
    query = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    items = db.scalars(query.order_by(Notification.created_at.desc()).limit(100))
    return [{"id": str(item.id), "type": item.notification_type, "title": item.title,
             "message": item.message, "payload": item.payload,
             "read_at": item.read_at.isoformat() if item.read_at else None} for item in items]


@router.post("/{notification_id}/read", status_code=204)
def mark_read(
    notification_id: UUID, db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    item = db.get(Notification, notification_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    item.read_at = datetime.now(UTC); db.commit(); return Response(status_code=204)
