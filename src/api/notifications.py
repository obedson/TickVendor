"""In-app notification API."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.database import get_db
from src.models import Notification, User

router = APIRouter(prefix="/notifications", tags=["notifications"])


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
