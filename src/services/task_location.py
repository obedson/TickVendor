"""One-shot, consented physical-task location evidence using attendance distance math."""
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.services.attendance import haversine_meters
from src.services.event import as_utc


class PhysicalLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    address: str = Field(default="", max_length=1000)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    radius_meters: int | None = Field(default=None, ge=10, le=10000)
    required: bool = False

    @model_validator(mode="after")
    def coordinates(self):
        if self.required and (self.latitude is None or self.longitude is None or self.radius_meters is None):
            raise ValueError("Required task GPS needs latitude, longitude and radius")
        return self


class LocationEvidence(BaseModel):
    latitude: Decimal = Field(ge=-90, le=90)
    longitude: Decimal = Field(ge=-180, le=180)
    accuracy_meters: float = Field(gt=0, le=10000)
    captured_at: datetime


def verify_location(task, evidence):
    configuration = task.task_config.get("geofence") if task.task_type == "physical" else None
    if not configuration or not configuration.get("required"):
        if evidence is not None:
            raise HTTPException(422, "This task does not request GPS evidence")
        return {}
    if evidence is None:
        raise HTTPException(422, "This task requires a fresh location check inside its geofence")
    config = PhysicalLocation.model_validate(configuration)
    point = LocationEvidence.model_validate(evidence)
    if abs((datetime.now(UTC) - as_utc(point.captured_at)).total_seconds()) > 120:
        raise HTTPException(422, "Location evidence expired; check your location again")
    if point.accuracy_meters > config.radius_meters:
        raise HTTPException(422, "Location accuracy is too low; retry with a more accurate position")
    distance = haversine_meters(point.latitude, point.longitude, config.latitude, config.longitude)
    if distance > config.radius_meters:
        raise HTTPException(422, "You are outside the task's permitted location")
    return {"verified": True, "distance_meters": round(distance), "accuracy_meters": round(point.accuracy_meters),
            "verified_at": datetime.now(UTC).isoformat()}
