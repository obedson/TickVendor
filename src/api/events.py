"""Event creation, management, publishing, and discovery routes."""

import os
from decimal import Decimal
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.api.auth import get_current_user
from src.database import get_db
from src.models import Event, EventStatus, User
from src.schemas.event import EventCreate, EventResponse, EventUpdate
from src.services.analytics import event_summary
from src.services.event import (
    create_event,
    discover_events,
    nearby_events,
    publish_event,
    soft_delete_event,
    update_event,
)
from src.uploads import safe_upload_name, validate_image_upload

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/{event_id}/analytics")
def event_analytics(
    event_id: UUID, db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return event_summary(db, event_id, current_user)


@router.post("/{event_id}/cover-image")
async def upload_cover_image(
    event_id: UUID, db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    upload: Annotated[UploadFile, File()],
):
    from src.services.event import get_event_for_management

    event = get_event_for_management(db, event_id, current_user)
    data = await validate_image_upload(upload)
    root = Path(os.environ.get("TICKEVEN_UPLOAD_DIR", "uploads")) / "events"
    root.mkdir(parents=True, exist_ok=True)
    filename = safe_upload_name(str(event.id), upload.filename, upload.content_type)
    (root / filename).write_bytes(data)
    event.cover_image_url = f"/uploads/events/{filename}"
    db.commit()
    from src.services.notification import audit
    audit(db, actor_id=current_user.id, community_id=event.community_id,
          action="event.cover_image_updated", target_type="event", target_id=event.id,
          metadata={"cover_image_url": event.cover_image_url})
    return {"cover_image_url": event.cover_image_url}


@router.get("/nearby")
def list_nearby_events(
    db: Annotated[Session, Depends(get_db)],
    latitude: Annotated[Decimal, Query(ge=-90, le=90)],
    longitude: Annotated[Decimal, Query(ge=-180, le=180)],
    radius_km: float = Query(default=25, gt=0, le=500), limit: int = Query(default=20, ge=1, le=100),
):
    return [{"id": str(event.id), "title": event.title, "starts_at": event.starts_at,
             "venue": {"name": event.venue.name, "city": event.venue.city},
             "distance_km": round(distance, 3)}
            for event, distance in nearby_events(db, latitude, longitude, radius_km, limit)]


@router.get("", response_model=list[EventResponse])
def list_events(
    db: Annotated[Session, Depends(get_db)],
    search: str | None = Query(default=None, max_length=200),
    category: str | None = Query(default=None, max_length=80),
    upcoming: bool = True,
    city: str | None = Query(default=None, max_length=120),
    price: str | None = Query(default=None, pattern="^(free|paid)$"),
    sort: str = Query(default="soonest", pattern="^(soonest|latest)$"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[Event]:
    return discover_events(db, search, category, upcoming, limit, offset, city, price, sort)


@router.get("/{event_id}", response_model=EventResponse)
def get_event(event_id: UUID, db: Annotated[Session, Depends(get_db)]) -> Event:
    event = db.scalar(
        select(Event).options(selectinload(Event.venue)).where(
            Event.id == event_id, Event.status == EventStatus.PUBLISHED, Event.deleted_at.is_(None)
        )
    )
    if event is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create(
    payload: EventCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Event:
    return create_event(db, payload, current_user)


@router.patch("/{event_id}", response_model=EventResponse)
def update(
    event_id: UUID,
    payload: EventUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Event:
    return update_event(db, event_id, payload, current_user)


@router.post("/{event_id}/publish", response_model=EventResponse)
def publish(
    event_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Event:
    return publish_event(db, event_id, current_user, True)


@router.delete("/{event_id}/publish", status_code=204)
def unpublish(
    event_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    publish_event(db, event_id, current_user, False)
    return Response(status_code=204)


@router.delete("/{event_id}", status_code=204)
def delete_event(
    event_id: UUID, db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    soft_delete_event(db, event_id, current_user)
    return Response(status_code=204)
