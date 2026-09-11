"""Attendance and verification policy administration."""

from datetime import datetime
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
)


class AttendanceConfigurationInput(BaseModel):
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
        "event_id": str(event.id)
    }


@router.patch("/{event_id}/attendance-config")
def update_attendance_config(community_id: UUID, event_id: UUID, payload: AttendanceConfigurationInput,
                             db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    require_community_role(db, community_id, user, MembershipRole.ADMIN)
    event = db.scalar(select(Event).where(Event.id == event_id, Event.community_id == community_id))
    if event is None: raise HTTPException(status_code=404, detail="Event not found")
    values = payload.model_dump(exclude_unset=True)
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
          target_type="event", target_id=event.id, metadata={"fields": sorted(values)}, commit=False)
    db.commit()
    return {field: getattr(event, field) for field in values} | {"event_id": str(event.id)}
