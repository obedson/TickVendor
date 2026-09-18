"""Event lifecycle service with tenant-aware authorization."""

import re
from datetime import UTC, datetime
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from src.authorization import require_community_role, require_resource_owner_or_super_admin
from src.models import (
    Community,
    Event,
    EventCategory,
    EventStatus,
    LocationType,
    Membership,
    MembershipRole,
    MembershipStatus,
    PlatformRole,
    TicketType,
    User,
    Venue,
)
from src.schemas.event import EventCreate, EventUpdate
from src.services.availability import require_available, visible_content
from src.services.notification import audit


def make_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "event"


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def event_distance_km(latitude: Decimal, longitude: Decimal, venue: Venue) -> float:
    phi1, phi2 = radians(float(latitude)), radians(float(venue.latitude))
    dphi = radians(float(venue.latitude - latitude))
    dlambda = radians(float(venue.longitude - longitude))
    value = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 6371 * 2 * asin(sqrt(value))


def nearby_events(db: Session, latitude: Decimal, longitude: Decimal, radius_km: float,
                  limit: int, user: User | None = None) -> list[tuple[Event, float]]:
    candidates = db.scalars(select(Event).options(selectinload(Event.venue)).join(Event.venue).where(
        *event_discovery_filters(user),
        Venue.latitude.is_not(None), Venue.longitude.is_not(None), Event.ends_at >= datetime.now(UTC),
    ).limit(500))
    result = [(event, event_distance_km(latitude, longitude, event.venue)) for event in candidates]
    return sorted((item for item in result if item[1] <= radius_km), key=lambda item: item[1])[:limit]


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
        max_peer_confirmations=payload.max_peer_confirmations,
        peer_confirmation_deadline=payload.peer_confirmation_deadline,
        required_verification_methods=payload.required_verification_methods,
        peer_selection_limit=payload.peer_selection_limit,
        peer_eligibility_statuses=payload.peer_eligibility_statuses,
    )
    db.add(event)
    db.commit()
    audit(db, actor_id=user.id, community_id=event.community_id, action="event.created",
          target_type="event", target_id=event.id, metadata={"title": event.title})
    return db.scalar(select(Event).options(selectinload(Event.venue)).where(Event.id == event.id))


def _authorize_event_management(db: Session, event: Event, user: User) -> None:
    if user.role != PlatformRole.SUPER_ADMIN:
        membership = require_community_role(db, event.community_id, user, MembershipRole.ORGANIZER)
        if membership.role != MembershipRole.ADMIN:
            require_resource_owner_or_super_admin(event.organizer_id, user)


def get_event_for_management(db: Session, event_id: UUID, user: User, *, include_deleted: bool = False) -> Event:
    """Load an event for the management endpoints.

    A deleted event stays hidden as unavailable for callers who cannot manage it. ``include_deleted``
    lets soft deletion distinguish an authorized repeat deletion (409) from a missing event (404)
    without revealing that distinction to anyone else.
    """
    event = db.scalar(select(Event).options(selectinload(Event.venue)).where(Event.id == event_id))
    if include_deleted and event is not None and event.deleted_at is not None:
        _authorize_event_management(db, event, user)
        return event
    require_available(db, event)
    _authorize_event_management(db, event, user)
    return event


def soft_delete_event(db: Session, event_id: UUID, user: User) -> None:
    event = get_event_for_management(db, event_id, user, include_deleted=True)
    if event.deleted_at is not None:
        raise HTTPException(status_code=409, detail="Event is already deleted")
    event.deleted_at = datetime.now(UTC)
    event.status = EventStatus.CANCELLED
    db.commit()
    audit(db, actor_id=user.id, community_id=event.community_id, action="event.deleted",
          target_type="event", target_id=event.id)


def update_event(db: Session, event_id: UUID, payload: EventUpdate, user: User) -> Event:
    event = get_event_for_management(db, event_id, user)
    if event.status not in {EventStatus.DRAFT, EventStatus.PUBLISHED}:
        raise HTTPException(status_code=409, detail="Event can no longer be edited")
    values = payload.model_dump(exclude_unset=True)
    if "category" in values:
        values["category"] = validate_category(db, values["category"])
    venue_values = values.pop("venue", None)
    if venue_values is not None:
        if event.venue is None:
            raise HTTPException(422, "Only an existing physical venue can be edited here")
        if event.geofence_enabled and (venue_values.get("latitude") is None or venue_values.get("longitude") is None):
            raise HTTPException(422, "Enabled geofencing requires venue coordinates")
        for field, value in venue_values.items():
            setattr(event.venue, field, value)
    for field, value in values.items():
        setattr(event, field, str(value) if field == "cover_image_url" and value else value)
    if event.ends_at <= event.starts_at:
        raise HTTPException(status_code=422, detail="ends_at must be after starts_at")
    db.commit()
    audit(db, actor_id=user.id, community_id=event.community_id, action="event.updated",
          target_type="event", target_id=event.id, metadata={"fields": sorted([*values, *(["venue"] if venue_values is not None else [])])})
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
    audit(db, actor_id=user.id, community_id=event.community_id,
          action="event.published" if publish else "event.unpublished",
          target_type="event", target_id=event.id)
    return event


def event_audience_filter(user: User | None):
    """Who may see an event at all, independent of its lifecycle state.

    A public community's events are world-readable, so guests and authenticated non-members both
    see them. A private community's events reach only that community's active members. Callers
    that need the lifecycle conditions as well should use :func:`event_discovery_filters`.
    """
    public_community = Event.community_id.in_(
        select(Community.id).where(Community.is_public.is_(True))
    )
    if user is None:
        return public_community
    return or_(
        public_community,
        Event.community_id.in_(select(Membership.community_id).where(
            Membership.user_id == user.id,
            Membership.status == MembershipStatus.ACTIVE,
        )),
    )


def event_discovery_filters(user: User | None) -> list:
    """Lifecycle and community-visibility conditions shared by every public event read.

    Anonymous and non-member callers receive nothing from a private community, whether they
    arrive through the listing, the nearby search, the single-event route or global search.
    """
    return [
        visible_content(Event),
        Event.status == EventStatus.PUBLISHED,
        Event.deleted_at.is_(None),
        event_audience_filter(user),
    ]


def discover_events(
    db: Session, search: str | None, category: str | None, upcoming: bool, limit: int, offset: int,
    city: str | None = None, price: str | None = None, sort: str = "soonest",
    user: User | None = None,
) -> list[Event]:
    query = select(Event).options(selectinload(Event.venue)).where(*event_discovery_filters(user))
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
