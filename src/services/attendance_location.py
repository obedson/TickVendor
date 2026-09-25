"""Location snapshots: browser-reported coordinates, never proof of physical identity."""

from fastapi import HTTPException

from src.services.notification import audit


def location_evidence(event, payload):
    from src.services.attendance import haversine_meters

    if payload is None or payload.latitude is None or payload.longitude is None:
        return None
    venue = event.venue
    distance = None
    if venue is not None and venue.latitude is not None and venue.longitude is not None:
        distance = haversine_meters(payload.latitude, payload.longitude, venue.latitude, venue.longitude)
    radius = event.geofence_radius_meters
    max_accuracy = event.geofence_max_accuracy_meters
    accuracy = payload.accuracy_meters
    outcome = "location_recorded"
    if event.geofence_enabled:
        if radius is None or distance is None:
            raise HTTPException(409, "This event's geofence is not fully configured; ask the organizer to check it")
        outcome = (
            "outside_geofence" if distance > radius else
            "accuracy_missing" if accuracy is None else
            "low_accuracy" if accuracy > max_accuracy else "verified"
        )
    return {
        "latitude": float(payload.latitude), "longitude": float(payload.longitude),
        "accuracy_meters": float(accuracy) if accuracy is not None else None,
        "distance_meters": round(distance, 2) if distance is not None else None,
        "radius_meters": radius,
        "max_accuracy_meters": max_accuracy,
        "venue_latitude": float(venue.latitude) if venue and venue.latitude is not None else None,
        "venue_longitude": float(venue.longitude) if venue and venue.longitude is not None else None,
        "outcome": outcome,
    }


def location_guidance(evidence):
    distance = evidence['distance_meters']
    radius = evidence['radius_meters']
    prefix = f"Reported position: {distance:.1f} m from the venue; allowed radius: {radius} m. "
    if evidence['outcome'] in {"low_accuracy", "accuracy_missing"}:
        accuracy = evidence['accuracy_meters']
        reading = f"{accuracy:.1f} m" if accuracy is not None else "not supplied"
        return prefix + (
            f"Device-reported accuracy: {reading}; automatic verification requires "
            f"{evidence['max_accuracy_meters']} m or better. This reading cannot verify your location, "
            "even if you are at the venue. Retry with precise location enabled on a GPS-capable phone, "
            "or ask event staff for an allowed verification method. Moving outdoors may not improve this device's reading."
        )
    return prefix + "The reported position is outside the event's permitted location. Ask event staff if the venue coordinates are incorrect."


def record_location(db, event, user, evidence, *, operation, commit=False):
    if evidence is not None:
        audit(db, actor_id=user.id, community_id=event.community_id,
              action="attendance.location_submitted", target_type="event", target_id=event.id,
              metadata={**evidence, "operation": operation}, commit=commit)
