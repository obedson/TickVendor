"""Event creation, management, publishing, and discovery routes."""

import hmac
import time
from decimal import Decimal
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.api.auth import get_current_user, get_optional_user
from src.config import settings
from src.database import get_db
from src.models import Event, EventCategory, User
from src.schemas.event import EventCreate, EventResponse, EventUpdate
from src.services.analytics import event_summary
from src.services.event import (
    create_event,
    discover_events,
    event_discovery_filters,
    nearby_events,
    publish_event,
    soft_delete_event,
    update_event,
)
from src.storage import (
    cover_delivery_url,
    event_cover_key,
    get_object_storage,
    local_signature,
    managed_cover_key,
)
from src.uploads import safe_upload_name, validate_image_upload

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/media/local", include_in_schema=False)
def local_cover(key: str, expires: int, signature: str):
    if settings.storage_provider != "local" or expires < int(time.time()) or not hmac.compare_digest(
        local_signature(key, expires).encode(), signature.encode()
    ):
        raise HTTPException(status_code=403, detail="Media link expired or invalid")
    root = Path(settings.storage_local_root).resolve()
    path = (root / key).resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Media not found")
    return FileResponse(path, headers={"Cache-Control": "private, no-store"})


@router.get("/locations/nigeria")
def nigeria_locations():
    from src.geography import nigeria_locations as locations
    return locations()


@router.get("/categories")
def list_event_categories(
    db: Annotated[Session, Depends(get_db)],
    active_only: bool = True,
):
    """Public endpoint — list event categories.

    Returns active categories by default. Pass active_only=false to include
    inactive categories (intended for authenticated super_admin use via
    PlatformAdmin; the /admin/categories route also serves that purpose with
    full mutation support).
    """
    stmt = select(EventCategory)
    if active_only:
        stmt = stmt.where(EventCategory.is_active.is_(True))
    stmt = stmt.order_by(EventCategory.name)
    categories = db.scalars(stmt).all()
    return [
        {"id": str(c.id), "slug": c.slug, "name": c.name, "is_active": c.is_active}
        for c in categories
    ]


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
    filename = safe_upload_name(uuid4().hex, upload.filename, upload.content_type)
    key = event_cover_key(event.community_id, event.id, filename)
    storage = get_object_storage()
    previous_key = managed_cover_key(event.cover_image_url, event.community_id, event.id)
    stored = storage.put(key, data, upload.content_type or "application/octet-stream")
    event.cover_image_url = stored.url
    from src.services.notification import audit
    try:
        audit(db, actor_id=current_user.id, community_id=event.community_id,
              action="event.cover_image_updated", target_type="event", target_id=event.id,
              metadata={"cover_image_url": event.cover_image_url}, commit=False)
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(key)
        raise
    if previous_key:
        storage.delete(previous_key)
    return {"cover_image_url": cover_delivery_url(event.cover_image_url, event.community_id, event.id)}


@router.delete("/{event_id}/cover-image", status_code=204)
def delete_cover_image(
    event_id: UUID, db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    from src.services.event import get_event_for_management
    from src.services.notification import audit
    event = get_event_for_management(db, event_id, current_user)
    key = managed_cover_key(event.cover_image_url, event.community_id, event.id)
    event.cover_image_url = None
    audit(db, actor_id=current_user.id, community_id=event.community_id,
          action="event.cover_image_removed", target_type="event", target_id=event.id, commit=False)
    db.commit()
    if key:
        get_object_storage().delete(key)
    return Response(status_code=204)


@router.get("/nearby")
def list_nearby_events(
    db: Annotated[Session, Depends(get_db)],
    latitude: Annotated[Decimal, Query(ge=-90, le=90)],
    longitude: Annotated[Decimal, Query(ge=-180, le=180)],
    radius_km: float = Query(default=25, gt=0, le=500), limit: int = Query(default=20, ge=1, le=100),
    viewer: Annotated[User | None, Depends(get_optional_user)] = None,
):
    return [{"id": str(event.id), "title": event.title, "starts_at": event.starts_at,
             "venue": {"name": event.venue.name, "city": event.venue.city},
             "distance_km": round(distance, 3)}
            for event, distance in nearby_events(db, latitude, longitude, radius_km, limit, viewer)]


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
    viewer: Annotated[User | None, Depends(get_optional_user)] = None,
) -> list[Event]:
    return discover_events(db, search, category, upcoming, limit, offset, city, price, sort, viewer)


@router.get("/{event_id}", response_model=EventResponse)
def get_event(
    event_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    viewer: Annotated[User | None, Depends(get_optional_user)] = None,
) -> Event:
    event = db.scalar(
        select(Event).options(selectinload(Event.venue)).where(
            Event.id == event_id, *event_discovery_filters(viewer),
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
    from src.services.event import get_event_for_management
    previous = get_event_for_management(db, event_id, current_user)
    old_key = managed_cover_key(previous.cover_image_url, previous.community_id, previous.id)
    event = update_event(db, event_id, payload, current_user)
    if (
        "cover_image_url" in payload.model_fields_set and old_key
        and managed_cover_key(event.cover_image_url, event.community_id, event.id) != old_key
    ):
        get_object_storage().delete(old_key)
    return event


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
