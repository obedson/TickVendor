"""Event and venue API schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    field_serializer,
    model_validator,
)

from src.models import EventStatus, LocationType


class VenueInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    address: str = Field(min_length=1, max_length=1000)
    city: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    country_code: str = Field(default="NG", min_length=2, max_length=2)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)


class EventCreate(BaseModel):
    community_id: UUID
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=10000)
    cover_image_url: HttpUrl | None = None
    category: str = Field(min_length=2, max_length=80)
    tags: list[str] = Field(default_factory=list, max_length=20)
    contact_email: EmailStr | None = None
    starts_at: datetime
    ends_at: datetime
    timezone: str = Field(default="Africa/Lagos", max_length=64)
    location_type: LocationType
    online_url: HttpUrl | None = None
    venue: VenueInput | None = None
    geofence_enabled: bool = False
    geofence_radius_meters: int | None = Field(default=None, ge=10, le=10000)
    check_in_opens_at: datetime | None = None
    check_in_closes_at: datetime | None = None
    peer_confirmation_enabled: bool = False
    confirmations_required: int = Field(default=0, ge=0, le=20)
    organizer_verification_enabled: bool = True
    qr_attendance_enabled: bool = True
    max_peer_confirmations: int | None = Field(default=None, ge=1, le=100)
    peer_confirmation_deadline: datetime | None = None
    required_verification_methods: list[str] = Field(default_factory=list, max_length=4)
    peer_selection_limit: int = Field(default=5, ge=1, le=20)
    peer_eligibility_statuses: list[str] = Field(default_factory=list, max_length=7)

    @model_validator(mode="after")
    def validate_event(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        if self.location_type in {LocationType.PHYSICAL, LocationType.HYBRID} and self.venue is None:
            raise ValueError("venue is required for physical or hybrid events")
        if self.location_type in {LocationType.ONLINE, LocationType.HYBRID} and self.online_url is None:
            raise ValueError("online_url is required for online or hybrid events")
        if self.geofence_enabled and (
            self.venue is None or self.venue.latitude is None or self.venue.longitude is None
        ):
            raise ValueError("geofencing requires venue coordinates")
        if self.check_in_opens_at and self.check_in_closes_at and self.check_in_closes_at <= self.check_in_opens_at:
            raise ValueError("check_in_closes_at must be after check_in_opens_at")
        return self


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, min_length=10, max_length=10000)
    cover_image_url: HttpUrl | None = None
    category: str | None = Field(default=None, min_length=2, max_length=80)
    tags: list[str] | None = Field(default=None, max_length=20)
    contact_email: EmailStr | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class VenueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    address: str
    city: str | None
    region: str | None
    country_code: str
    latitude: Decimal | None
    longitude: Decimal | None


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    community_id: UUID
    organizer_id: UUID
    title: str
    slug: str
    description: str
    cover_image_url: str | None
    category: str
    tags: list[str]
    contact_email: str | None
    starts_at: datetime
    ends_at: datetime
    timezone: str
    location_type: LocationType
    online_url: str | None
    status: EventStatus
    published_at: datetime | None
    venue: VenueResponse | None
    geofence_enabled: bool
    required_verification_methods: list[str]

    @field_serializer("cover_image_url")
    def deliver_cover(self, value: str | None) -> str | None:
        from src.storage import cover_delivery_url
        return cover_delivery_url(value, self.community_id, self.id)
