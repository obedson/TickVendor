"""Event staff delegation: narrow, per-event operational authority.

``EventStaff`` is what lets an Admin delegate one operational job on one event without widening
anybody's community membership role. Until now the model was only ever *read* (three authorization
sites) and never written, so the delegation it represents could not actually be granted. This
service is that missing write path.

Appointment itself is deliberately not delegable: only the event's owner, a community Admin, or a
Super Admin may grant or revoke staff, and an existing staff member cannot appoint further staff.
Otherwise the narrow grant would silently become a way to hand out broad authority.
"""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.authorization import require_event_ownership_authority
from src.models import (
    Community,
    Event,
    EventStaff,
    EventStaffRole,
    Membership,
    MembershipStatus,
    Profile,
    User,
)
from src.services.notification import audit


def _load_event(db: Session, event_id) -> Event:
    event = db.get(Event, event_id)
    if event is None or event.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Event not found")
    community = db.get(Community, event.community_id)
    if event.is_suspended or community is None or not community.is_active or community.deleted_at is not None:
        raise HTTPException(status_code=403, detail="This content or community is suspended")
    return event


def _staff_payload(item: EventStaff, profile: Profile | None) -> dict:
    """Minimum operational shape. Staff lists never carry contact details."""
    return {
        "id": str(item.id),
        "event_id": str(item.event_id),
        "user_id": str(item.user_id),
        "role": item.role.value,
        "is_active": item.is_active,
        "display_name": profile.display_name if profile else "Community member",
        "username": profile.username if profile else None,
        "created_at": item.created_at,
    }


def list_staff(db: Session, event_id, actor: User) -> list[dict]:
    event = _load_event(db, event_id)
    require_event_ownership_authority(db, event, actor)
    rows = db.execute(
        select(EventStaff, Profile)
        .outerjoin(Profile, Profile.user_id == EventStaff.user_id)
        .where(EventStaff.event_id == event.id)
        .order_by(EventStaff.created_at, EventStaff.id)
    ).all()
    return [_staff_payload(item, profile) for item, profile in rows]


def _eligible_member(db: Session, event: Event, user_id) -> Membership:
    """Resolve the assignee inside this community only.

    A user who is not an active member of *this* community is indistinguishable from a user who
    does not exist, so cross-community assignment cannot be probed for account existence.
    """
    target = db.get(User, user_id)
    if target is None or not target.is_active:
        raise HTTPException(status_code=404, detail="Community member not found")
    membership = db.scalar(select(Membership).where(
        Membership.community_id == event.community_id,
        Membership.user_id == user_id,
        Membership.status == MembershipStatus.ACTIVE,
    ))
    if membership is None:
        raise HTTPException(status_code=404, detail="Community member not found")
    return membership


def assign_staff(db: Session, event_id, actor: User, user_id, role: EventStaffRole) -> dict:
    event = _load_event(db, event_id)
    require_event_ownership_authority(db, event, actor)
    try:
        staff_role = EventStaffRole(role)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Unknown event staff role") from exc
    membership = _eligible_member(db, event, user_id)
    item = db.scalar(select(EventStaff).where(
        EventStaff.event_id == event.id, EventStaff.user_id == membership.user_id,
    ))
    if item is not None and item.role == staff_role and item.is_active:
        return _staff_payload(item, db.scalar(select(Profile).where(Profile.user_id == item.user_id)))
    if item is None:
        item = EventStaff(event_id=event.id, user_id=membership.user_id, role=staff_role, is_active=True)
        db.add(item)
        action = "event.staff.assigned"
    else:
        item.role = staff_role
        item.is_active = True
        action = "event.staff.updated"
    db.flush()
    audit(db, actor_id=actor.id, community_id=event.community_id, action=action,
          target_type="event_staff", target_id=item.id,
          metadata={"event_id": str(event.id), "user_id": str(item.user_id), "role": staff_role.value},
          commit=False)
    db.commit()
    return _staff_payload(item, db.scalar(select(Profile).where(Profile.user_id == item.user_id)))


def revoke_staff(db: Session, event_id, actor: User, staff_id) -> dict:
    event = _load_event(db, event_id)
    require_event_ownership_authority(db, event, actor)
    item = db.get(EventStaff, staff_id)
    # A foreign staff id is "not found" rather than "forbidden", so staff ids cannot be probed
    # across events.
    if item is None or item.event_id != event.id:
        raise HTTPException(status_code=404, detail="Event staff assignment not found")
    profile = db.scalar(select(Profile).where(Profile.user_id == item.user_id))
    if not item.is_active:
        return _staff_payload(item, profile)
    item.is_active = False
    audit(db, actor_id=actor.id, community_id=event.community_id, action="event.staff.revoked",
          target_type="event_staff", target_id=item.id,
          metadata={"event_id": str(event.id), "user_id": str(item.user_id), "role": item.role.value},
          commit=False)
    db.commit()
    return _staff_payload(item, profile)
