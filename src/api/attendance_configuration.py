"""Attendance and verification policy administration."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.authorization import require_community_role
from src.database import get_db
from src.models import Event, MembershipRole, User
from src.services.notification import audit

router = APIRouter(prefix="/communities/{community_id}/events", tags=["attendance"])

CONFIGURATION_FIELDS = (
    "qr_attendance_enabled",
    "peer_confirmation_enabled",
    "confirmations_required",
    "organizer_verification_enabled",
    "geofence_enabled",
    "geofence_radius_meters",
    "max_peer_confirmations",
    "peer_confirmation_deadline",
    "peer_selection_limit",
    "peer_eligibility_statuses",
    "required_verification_methods",
    "self_check_in_enabled",
    "self_checkout_enabled",
    "checkout_opens_at",
)


class AttendanceConfigurationInput(BaseModel):
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    qr_attendance_enabled: bool | None = None
    peer_confirmation_enabled: bool | None = None
    confirmations_required: int | None = Field(default=None, ge=0, le=100)
    organizer_verification_enabled: bool | None = None
    geofence_enabled: bool | None = None
    geofence_radius_meters: int | None = Field(default=None, ge=10, le=100000)
    max_peer_confirmations: int | None = Field(default=None, ge=1, le=100)
    peer_confirmation_deadline: datetime | None = None
    peer_selection_limit: int | None = Field(default=None, ge=1, le=100)
    peer_eligibility_statuses: list[str] | None = Field(default=None, max_length=20)
    required_verification_methods: list[str] | None = Field(default=None, max_length=10)
    self_check_in_enabled: bool | None = None
    self_checkout_enabled: bool | None = None
    checkout_opens_at: datetime | None = None

    @field_validator("required_verification_methods")
    @classmethod
    def valid_methods(cls, value):
        allowed = {"qr", "gps", "peer", "organizer"}
        if value is not None and not set(value).issubset(allowed):
            raise ValueError("unsupported verification method")
        return value

    @model_validator(mode="after")
    def validate_combinations(self):
        if self.geofence_enabled and self.geofence_radius_meters is None:
            raise ValueError("geofence radius is required when enabling geofence")
        if self.self_checkout_enabled and self.self_check_in_enabled is False:
            raise ValueError("self checkout requires self check-in")
        return self


@router.get("/{event_id}/attendance-config")
def get_attendance_config(
    community_id: UUID,
    event_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    require_community_role(db, community_id, user, MembershipRole.ORGANIZER)
    event = db.scalar(select(Event).where(Event.id == event_id, Event.community_id == community_id))
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return {field: getattr(event, field) for field in CONFIGURATION_FIELDS} | {
        "event_id": str(event.id), "latitude": event.venue.latitude if event.venue else None, "longitude": event.venue.longitude if event.venue else None
    }


@router.patch("/{event_id}/attendance-config")
def update_attendance_config(community_id: UUID, event_id: UUID, payload: AttendanceConfigurationInput,
                             db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    require_community_role(db, community_id, user, MembershipRole.ADMIN)
    event = db.scalar(select(Event).where(Event.id == event_id, Event.community_id == community_id))
    if event is None: raise HTTPException(status_code=404, detail="Event not found")
    values = payload.model_dump(exclude_unset=True)
    if any(value is None for key, value in values.items() if key not in {"latitude", "longitude", "peer_confirmation_deadline", "checkout_opens_at"}):
        raise HTTPException(422, "Attendance policy fields cannot be null")
    coordinates = {key: values.pop(key) for key in ("latitude", "longitude") if key in values}
    if event.venue is None and not any(value is not None for value in coordinates.values()):
        coordinates = {}
    if coordinates:
        if event.venue is None:
            raise HTTPException(422, "GPS requires a physical venue")
        for key, value in coordinates.items():
            setattr(event.venue, key, value)
    if values.get("geofence_enabled", event.geofence_enabled) and (event.venue is None or event.venue.latitude is None or event.venue.longitude is None):
        raise HTTPException(422, "GPS requires venue latitude and longitude")
    peer_enabled = values.get("peer_confirmation_enabled", event.peer_confirmation_enabled)
    required_methods = values.get("required_verification_methods", event.required_verification_methods)
    confirmations_required = values.get("confirmations_required", event.confirmations_required)
    enabled_methods = {"qr": values.get("qr_attendance_enabled", event.qr_attendance_enabled),
                       "gps": values.get("geofence_enabled", event.geofence_enabled),
                       "peer": peer_enabled,
                       "organizer": values.get("organizer_verification_enabled", event.organizer_verification_enabled)}
    missing_methods = [method for method in required_methods if not enabled_methods.get(method, False)]
    if missing_methods:
        raise HTTPException(status_code=422, detail=f"Required verification method is disabled: {missing_methods[0]}")
    if "peer" in required_methods and not peer_enabled:
        raise HTTPException(status_code=422, detail="Peer verification requires peer confirmation")
    if peer_enabled and "peer" in required_methods and confirmations_required < 1:
        raise HTTPException(status_code=422, detail="At least one peer confirmation is required")
    max_peer_confirmations = values.get("max_peer_confirmations", event.max_peer_confirmations)
    if "peer" in required_methods and max_peer_confirmations is not None and max_peer_confirmations < confirmations_required:
        raise HTTPException(status_code=422, detail="Peer confirmation limit cannot be below required confirmations")
    if values.get("peer_confirmation_enabled") and values.get("max_peer_confirmations") == 0:
        raise HTTPException(status_code=422, detail="Peer confirmation limit must be positive")
    if values.get("peer_confirmation_enabled") and values.get("peer_selection_limit") == 0:
        raise HTTPException(status_code=422, detail="Peer selection limit must be positive")
    for field, value in values.items(): setattr(event, field, value)
    audit(db, actor_id=user.id, community_id=community_id, action="attendance_configuration.updated",
          target_type="event", target_id=event.id, metadata={"fields": sorted([*values, *coordinates])}, commit=False)
    db.commit()
    # Coordinates were written to the venue, not the event; echo them so the PATCH response
    # matches the GET response and callers do not see their saved venue coordinates disappear.
    return {field: getattr(event, field) for field in values} | {
        "event_id": str(event.id), "latitude": event.venue.latitude if event.venue else None,
        "longitude": event.venue.longitude if event.venue else None}
