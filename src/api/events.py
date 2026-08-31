"""Event creation, management, publishing, and discovery routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.api.auth import get_current_user
from src.database import get_db
from src.models import Event, EventStatus, User
from src.schemas.event import EventCreate, EventResponse, EventUpdate
from src.services.event import create_event, discover_events, publish_event, update_event

router = APIRouter(prefix="/events", tags=["events"])


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
            Event.id == event_id, Event.status == EventStatus.PUBLISHED
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
