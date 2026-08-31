"""Event lifecycle service with tenant-aware authorization."""

import re
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from src.authorization import require_community_role, require_resource_owner_or_super_admin
from src.models import (
    Event,
    EventCategory,
    EventStatus,
    LocationType,
    MembershipRole,
    PlatformRole,
    TicketType,
    User,
    Venue,
)
from src.schemas.event import EventCreate, EventUpdate


def make_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "event"


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def unique_slug(db: Session, title: str) -> str:
    base = make_slug(title)
    candidate = base
    counter = 2
    while db.scalar(select(Event.id).where(Event.slug == candidate)) is not None:
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate


def validate_category(db: Session, category: str) -> str:
    normalized = make_slug(category)
    configured = db.scalar(
        select(EventCategory).where(EventCategory.slug == normalized, EventCategory.is_active.is_(True))
    )
    if configured is None:
        raise HTTPException(status_code=422, detail="Unknown or inactive event category")
    return normalized


def create_event(db: Session, payload: EventCreate, user: User) -> Event:
    require_community_role(db, payload.community_id, user, MembershipRole.ORGANIZER)
    venue = Venue(**payload.venue.model_dump()) if payload.venue else None
    event = Event(
        community_id=payload.community_id,
        organizer_id=user.id,
        venue=venue,
        title=payload.title,
        slug=unique_slug(db, payload.title),
        description=payload.description,
        cover_image_url=str(payload.cover_image_url) if payload.cover_image_url else None,
        category=validate_category(db, payload.category),
        tags=payload.tags,
        contact_email=str(payload.contact_email) if payload.contact_email else None,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        timezone=payload.timezone,
        location_type=payload.location_type,
        online_url=str(payload.online_url) if payload.online_url else None,
        geofence_enabled=payload.geofence_enabled,
        geofence_radius_meters=payload.geofence_radius_meters,
        check_in_opens_at=payload.check_in_opens_at,
        check_in_closes_at=payload.check_in_closes_at,
        peer_confirmation_enabled=payload.peer_confirmation_enabled,
        confirmations_required=payload.confirmations_required,
        organizer_verification_enabled=payload.organizer_verification_enabled,
        qr_attendance_enabled=payload.qr_attendance_enabled,
    )
    db.add(event)
    db.commit()
    return db.scalar(select(Event).options(selectinload(Event.venue)).where(Event.id == event.id))


def get_event_for_management(db: Session, event_id: UUID, user: User) -> Event:
    event = db.scalar(select(Event).options(selectinload(Event.venue)).where(Event.id == event_id))
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if user.role != PlatformRole.SUPER_ADMIN:
        membership = require_community_role(db, event.community_id, user, MembershipRole.ORGANIZER)
        if membership.role != MembershipRole.ADMIN:
            require_resource_owner_or_super_admin(event.organizer_id, user)
    return event


def update_event(db: Session, event_id: UUID, payload: EventUpdate, user: User) -> Event:
    event = get_event_for_management(db, event_id, user)
    if event.status not in {EventStatus.DRAFT, EventStatus.PUBLISHED}:
        raise HTTPException(status_code=409, detail="Event can no longer be edited")
    values = payload.model_dump(exclude_unset=True)
    if "category" in values:
        values["category"] = validate_category(db, values["category"])
    for field, value in values.items():
        setattr(event, field, str(value) if field == "cover_image_url" and value else value)
    if event.ends_at <= event.starts_at:
        raise HTTPException(status_code=422, detail="ends_at must be after starts_at")
    db.commit()
    return event


def publish_event(db: Session, event_id: UUID, user: User, publish: bool) -> Event:
    event = get_event_for_management(db, event_id, user)
    if publish:
        if as_utc(event.ends_at) <= datetime.now(UTC):
            raise HTTPException(status_code=409, detail="Past events cannot be published")
        if event.location_type in {LocationType.PHYSICAL, LocationType.HYBRID} and event.venue is None:
            raise HTTPException(status_code=409, detail="Venue is required before publishing")
        event.status = EventStatus.PUBLISHED
        event.published_at = datetime.now(UTC)
    else:
        if event.status != EventStatus.PUBLISHED:
            raise HTTPException(status_code=409, detail="Only published events can be unpublished")
        event.status = EventStatus.DRAFT
        event.published_at = None
    db.commit()
    return event


def discover_events(
    db: Session, search: str | None, category: str | None, upcoming: bool, limit: int, offset: int,
    city: str | None = None, price: str | None = None, sort: str = "soonest",
) -> list[Event]:
    query = select(Event).options(selectinload(Event.venue)).where(Event.status == EventStatus.PUBLISHED)
    if search:
        pattern = f"%{search.strip().lower()}%"
        query = query.where(
            func.lower(Event.title).like(pattern) | func.lower(Event.description).like(pattern)
        )
    if category:
        query = query.where(Event.category == make_slug(category))
    if upcoming:
        query = query.where(Event.ends_at >= datetime.now(UTC))
    if city:
        query = query.join(Event.venue).where(func.lower(Venue.city) == city.lower())
    if price == "free":
        query = query.where(~select(TicketType.id).where(
            TicketType.event_id == Event.id, TicketType.price > 0
        ).exists())
    elif price == "paid":
        query = query.where(select(TicketType.id).where(
            TicketType.event_id == Event.id, TicketType.price > 0
        ).exists())
    ordering = Event.starts_at.desc() if sort == "latest" else Event.starts_at.asc()
    return list(db.scalars(query.order_by(ordering).offset(offset).limit(limit)))
