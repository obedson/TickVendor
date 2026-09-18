"""Configurable ticket perks, eligibility rules, and atomic redemption credentials.

Eligibility is always decided by the server from persisted state and server time. A credential
is issued only after eligibility is proven, is short-lived, is single-use, and is stored as a
SHA-256 digest so it can never be recovered from the database. Staff validation re-checks every
configured condition and takes a row lock, so two staff devices cannot redeem one perk twice.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models import (
    Attendance,
    AttendanceStatus,
    Entitlement,
    EntitlementRedemption,
    Event,
    EventStatus,
    Profile,
    RedemptionMode,
    RedemptionStatus,
    Ticket,
    TicketAssignmentState,
    TicketEntitlement,
    TicketEntitlementStatus,
    TicketStatus,
    TicketType,
    User,
)
from src.services.attendance import haversine_meters
from src.services.event import as_utc
from src.services.notification import audit, notify
from src.services.ticket_attendance import require_event_staff

REDEMPTION_TTL = timedelta(minutes=10)
# Excludes visually ambiguous characters so a 4-character code can be read aloud.
CODE_ALPHABET = "ACDEFGHJKLMNPQRTUVWXY34679"
_INVALID_TICKET_STATUSES = {TicketStatus.CANCELLED, TicketStatus.REFUNDED, TicketStatus.EXPIRED}


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _generate_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(4))


def _display_name(db: Session, user_id) -> str:
    profile = db.scalar(select(Profile).where(Profile.user_id == user_id))
    if profile is None:
        return "Community member"
    return f"{profile.display_name} (@{profile.username})"


# ── Configuration ────────────────────────────────────────────────────────────

def create_entitlement(db: Session, event: Event, payload, user: User) -> Entitlement:
    ticket_type = db.get(TicketType, payload.ticket_type_id)
    if ticket_type is None or ticket_type.event_id != event.id:
        raise HTTPException(status_code=404, detail="Ticket type not found")
    require_event_staff(db, event, user)
    model = Entitlement(event_id=event.id, created_by_id=user.id, **payload.model_dump())
    db.add(model)
    db.flush()
    audit(db, actor_id=user.id, community_id=event.community_id, action="entitlement.created",
          target_type="entitlement", target_id=model.id,
          metadata={"event_id": str(event.id), "ticket_type_id": str(ticket_type.id)}, commit=False)
    db.commit()
    _sync_type(db, ticket_type.id)
    return model


def update_entitlement(db: Session, event: Event, entitlement: Entitlement, payload, user: User) -> Entitlement:
    if entitlement is None or entitlement.event_id != event.id:
        raise HTTPException(status_code=404, detail="Benefit not found")
    require_event_staff(db, event, user)
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(entitlement, key, value)
    audit(db, actor_id=user.id, community_id=event.community_id, action="entitlement.updated",
          target_type="entitlement", target_id=entitlement.id,
          metadata={"fields": sorted(changes)}, commit=False)
    db.commit()
    if not entitlement.is_active:
        for state in db.scalars(select(TicketEntitlement).where(
            TicketEntitlement.entitlement_id == entitlement.id,
            TicketEntitlement.status == TicketEntitlementStatus.AVAILABLE,
        )):
            state.status = TicketEntitlementStatus.REVOKED
        db.commit()
    return entitlement


def _sync_type(db: Session, ticket_type_id) -> int:
    """Issue a state row for every ticket of a type that lacks one for each active perk."""
    entitlements = list(db.scalars(select(Entitlement).where(
        Entitlement.ticket_type_id == ticket_type_id, Entitlement.is_active.is_(True)
    )))
    if not entitlements:
        return 0
    created = 0
    for ticket in db.scalars(select(Ticket).where(Ticket.ticket_type_id == ticket_type_id)):
        created += sync_ticket_entitlements(db, ticket, commit=False)
    db.commit()
    return created


def sync_ticket_entitlements(db: Session, ticket: Ticket, *, commit: bool = False) -> int:
    """Idempotently attach the ticket type's active perks to one issued ticket."""
    entitlements = list(db.scalars(select(Entitlement).where(
        Entitlement.ticket_type_id == ticket.ticket_type_id, Entitlement.is_active.is_(True)
    )))
    if not entitlements:
        return 0
    existing = {
        row.entitlement_id for row in db.scalars(
            select(TicketEntitlement).where(TicketEntitlement.ticket_id == ticket.id)
        )
    }
    created = 0
    for entitlement in entitlements:
        if entitlement.id in existing:
            continue
        db.add(TicketEntitlement(
            ticket_id=ticket.id, entitlement_id=entitlement.id,
            quantity_total=max(1, entitlement.quantity), quantity_redeemed=0,
            status=TicketEntitlementStatus.AVAILABLE,
        ))
        created += 1
    if created:
        db.flush()
    if commit:
        db.commit()
    return created


# ── Eligibility ──────────────────────────────────────────────────────────────

def _geofence_check(event: Event, point) -> str | None:
    if event.geofence_radius_meters is None or event.venue is None:
        return "Must be inside venue"
    if event.venue.latitude is None or event.venue.longitude is None:
        return "Must be inside venue"
    if point is None or point.latitude is None or point.longitude is None:
        return "Location is required; allow location access and try again"
    distance = haversine_meters(
        point.latitude, point.longitude, event.venue.latitude, event.venue.longitude
    )
    if distance > event.geofence_radius_meters:
        return "Must be inside venue"
    return None


def evaluate_eligibility(
    db: Session,
    ticket: Ticket,
    entitlement: Entitlement,
    state: TicketEntitlement,
    *,
    point=None,
    now: datetime | None = None,
) -> tuple[str, str | None]:
    """Return ``(status, locked_reason)`` where status is available/locked/redeemed/expired/revoked."""
    now = now or datetime.now(UTC)
    if state.status == TicketEntitlementStatus.REVOKED:
        return "revoked", "This benefit is no longer offered"
    if ticket.status in _INVALID_TICKET_STATUSES:
        return "locked", "Ticket is no longer valid"
    if not entitlement.is_active:
        return "locked", "This benefit is not available"
    if state.quantity_redeemed >= max(1, entitlement.max_redemptions_per_ticket):
        return "redeemed", "Already redeemed"
    if state.status == TicketEntitlementStatus.EXPIRED:
        return "expired", "This benefit has expired"
    attendance = db.scalar(select(Attendance).where(
        Attendance.event_id == ticket.event_id, Attendance.user_id == ticket.attendee_id
    ))
    if entitlement.requires_check_in:
        if attendance is None or attendance.checked_in_at is None:
            return "locked", "Check in first"
        if attendance.status == AttendanceStatus.REJECTED:
            return "locked", "Your attendance was rejected"
    if entitlement.redemption_starts_at and now < as_utc(entitlement.redemption_starts_at):
        return "locked", f"Available from {as_utc(entitlement.redemption_starts_at).strftime('%H:%M')}"
    if entitlement.redemption_ends_at and now > as_utc(entitlement.redemption_ends_at):
        return "expired", "The redemption window has closed"
    if entitlement.requires_checkout and (
        attendance is None or attendance.checked_out_at is None
    ):
        return "locked", "Available after checkout"
    if entitlement.min_attendance_minutes:
        if attendance is None or attendance.checked_in_at is None:
            return "locked", "Check in first"
        elapsed = attendance.duration_seconds
        if elapsed is None:
            elapsed = int((now - as_utc(attendance.checked_in_at)).total_seconds())
        if elapsed < entitlement.min_attendance_minutes * 60:
            return "locked", "Minimum attendance not yet reached"
    if entitlement.requires_geofence:
        reason = _geofence_check(db.get(Event, ticket.event_id), point)
        if reason:
            return "locked", reason
    return "available", None


def entitlement_state(
    db: Session,
    ticket: Ticket,
    entitlement: Entitlement,
    state: TicketEntitlement,
    *,
    point=None,
) -> dict:
    status, reason = evaluate_eligibility(db, ticket, entitlement, state, point=point)
    return {
        "id": str(entitlement.id),
        "name": entitlement.name,
        "description": entitlement.description,
        "quantity": entitlement.quantity,
        "redemption_mode": entitlement.redemption_mode.value,
        "redemption_starts_at": entitlement.redemption_starts_at,
        "redemption_ends_at": entitlement.redemption_ends_at,
        "requires_check_in": entitlement.requires_check_in,
        "requires_checkout": entitlement.requires_checkout,
        "min_attendance_minutes": entitlement.min_attendance_minutes,
        "requires_geofence": entitlement.requires_geofence,
        "requires_staff_validation": entitlement.requires_staff_validation,
        "remaining": max(0, max(1, entitlement.max_redemptions_per_ticket) - state.quantity_redeemed),
        "status": status,
        "locked_reason": reason,
        "last_redeemed_at": state.last_redeemed_at,
    }


def list_ticket_entitlements(db: Session, ticket: Ticket, *, point=None) -> list[dict]:
    sync_ticket_entitlements(db, ticket, commit=True)
    rows = db.execute(select(TicketEntitlement, Entitlement).join(
        Entitlement, Entitlement.id == TicketEntitlement.entitlement_id
    ).where(TicketEntitlement.ticket_id == ticket.id).order_by(Entitlement.name)).all()
    return [entitlement_state(db, ticket, entitlement, state, point=point) for state, entitlement in rows]


# ── Credential issuance ──────────────────────────────────────────────────────

def _require_holder(ticket: Ticket, user: User) -> None:
    if ticket.attendee_id != user.id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.assignment_state != TicketAssignmentState.CLAIMED:
        raise HTTPException(
            status_code=409, detail="This ticket has no assigned attendee yet"
        )


def _cancel_pending(db: Session, state: TicketEntitlement) -> None:
    now = datetime.now(UTC)
    for row in db.scalars(select(EntitlementRedemption).where(
        EntitlementRedemption.ticket_entitlement_id == state.id,
        EntitlementRedemption.status == RedemptionStatus.ISSUED,
    ).with_for_update()):
        row.status = RedemptionStatus.CANCELLED if as_utc(row.expires_at) > now else RedemptionStatus.EXPIRED


def redeem_entitlement(
    db: Session, event_id: UUID, ticket: Ticket, entitlement_id, user: User, *, point=None
) -> dict:
    ticket = db.scalar(select(Ticket).where(Ticket.id == ticket.id).with_for_update())
    if ticket is None or ticket.event_id != event_id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    _require_holder(ticket, user)
    event = db.get(Event, event_id)
    if event is None or event.status != EventStatus.PUBLISHED:
        raise HTTPException(status_code=404, detail="Event not found")
    sync_ticket_entitlements(db, ticket, commit=False)
    state = db.scalar(select(TicketEntitlement).where(
        TicketEntitlement.ticket_id == ticket.id,
        TicketEntitlement.entitlement_id == entitlement_id,
    ).with_for_update())
    if state is None:
        raise HTTPException(status_code=404, detail="Benefit not found")
    entitlement = db.get(Entitlement, entitlement_id)
    now = datetime.now(UTC)
    status, reason = evaluate_eligibility(db, ticket, entitlement, state, point=point, now=now)

    if not entitlement.requires_staff_validation:
        if status != "available":
            db.commit()
            raise HTTPException(status_code=409, detail=reason or "This benefit is not available yet")
        _apply_redemption(state, entitlement, now)
        audit(db, actor_id=user.id, community_id=event.community_id,
              action="entitlement.redeemed", target_type="entitlement", target_id=entitlement.id,
              metadata={"ticket_id": str(ticket.id), "method": "self"}, commit=False)
        db.commit()
        notify(db, ticket.attendee_id, "benefit_redeemed", "Benefit redeemed",
               f"{entitlement.name} was redeemed for {event.title}.",
               {"ticket_id": str(ticket.id), "entitlement_id": str(entitlement.id)},
               community_id=event.community_id, commit=False)
        db.commit()
        return {"status": "redeemed", "entitlement": entitlement.name,
                "remaining": max(0, max(1, entitlement.max_redemptions_per_ticket) - state.quantity_redeemed)}

    if status != "available":
        db.commit()
        raise HTTPException(status_code=409, detail=reason or "This benefit is not available yet")

    _cancel_pending(db, state)
    code = _generate_code()
    qr_payload = f"{uuid4().hex}.{secrets.token_urlsafe(24)}"
    redemption = EntitlementRedemption(
        ticket_entitlement_id=state.id, event_id=event_id, ticket_id=ticket.id,
        entitlement_id=entitlement.id, holder_id=ticket.attendee_id,
        code_hash=_hash(code), qr_token_hash=_hash(qr_payload),
        status=RedemptionStatus.ISSUED, expires_at=now + REDEMPTION_TTL,
    )
    db.add(redemption)
    audit(db, actor_id=user.id, community_id=event.community_id, action="entitlement.credential_issued",
          target_type="entitlement", target_id=entitlement.id,
          metadata={"ticket_id": str(ticket.id), "redemption_id": str(redemption.id)}, commit=False)
    db.commit()
    return {
        "status": "issued",
        "entitlement": entitlement.name,
        "code": code if entitlement.redemption_mode in {RedemptionMode.CODE, RedemptionMode.EITHER} else None,
        "qr_payload": qr_payload if entitlement.redemption_mode in {RedemptionMode.QR, RedemptionMode.EITHER} else None,
        "expires_at": redemption.expires_at,
    }


def _apply_redemption(
    state: TicketEntitlement, entitlement: Entitlement, now: datetime
) -> None:
    state.quantity_redeemed += 1
    state.last_redeemed_at = now
    if state.quantity_redeemed >= max(1, entitlement.max_redemptions_per_ticket):
        state.status = TicketEntitlementStatus.REDEEMED


# ── Staff validation ─────────────────────────────────────────────────────────

def _resolve_credential(db: Session, event_id: UUID, code: str | None, qr_payload: str | None):
    if code:
        digest = _hash(code.strip().upper())
        return db.scalar(select(EntitlementRedemption).where(
            EntitlementRedemption.event_id == event_id, EntitlementRedemption.code_hash == digest
        ).with_for_update())
    if qr_payload:
        return db.scalar(select(EntitlementRedemption).where(
            EntitlementRedemption.event_id == event_id,
            EntitlementRedemption.qr_token_hash == _hash(qr_payload.strip()),
        ).with_for_update())
    raise HTTPException(status_code=422, detail="Enter a redemption code or scan a redemption QR")


def validate_redemption(
    db: Session, event_id: UUID, staff: User, *, code: str | None = None,
    qr_payload: str | None = None, point=None,
) -> dict:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    require_event_staff(db, event, staff)
    redemption = _resolve_credential(db, event_id, code, qr_payload)
    if redemption is None:
        raise HTTPException(status_code=404, detail="Invalid or unknown redemption credential")
    now = datetime.now(UTC)
    if redemption.status == RedemptionStatus.REDEEMED:
        raise HTTPException(status_code=409, detail="This benefit has already been redeemed")
    if redemption.status == RedemptionStatus.CANCELLED:
        raise HTTPException(status_code=409, detail="This redemption credential was replaced")
    if as_utc(redemption.expires_at) <= now:
        redemption.status = RedemptionStatus.EXPIRED
        db.commit()
        raise HTTPException(status_code=409, detail="This redemption credential has expired")
    state = db.scalar(select(TicketEntitlement).where(
        TicketEntitlement.id == redemption.ticket_entitlement_id
    ).with_for_update())
    entitlement = db.get(Entitlement, redemption.entitlement_id)
    ticket = db.get(Ticket, redemption.ticket_id)
    if state is None or entitlement is None or ticket is None:
        raise HTTPException(status_code=404, detail="Invalid or unknown redemption credential")
    status, reason = evaluate_eligibility(db, ticket, entitlement, state, point=point, now=now)
    if status != "available":
        raise HTTPException(status_code=409, detail=reason or "This benefit is not redeemable")
    redemption.status = RedemptionStatus.REDEEMED
    redemption.redeemed_at = now
    redemption.redeemed_by_id = staff.id
    redemption.redeemed_method = "qr" if qr_payload else "code"
    _apply_redemption(state, entitlement, now)
    ticket_type = db.get(TicketType, ticket.ticket_type_id)
    audit(db, actor_id=staff.id, community_id=event.community_id, action="entitlement.redeemed",
          target_type="entitlement", target_id=entitlement.id,
          metadata={"ticket_id": str(ticket.id), "redemption_id": str(redemption.id),
                    "staff_id": str(staff.id), "method": redemption.redeemed_method}, commit=False)
    db.commit()
    notify(db, ticket.attendee_id, "benefit_redeemed", "Benefit redeemed",
           f"{entitlement.name} was redeemed at {event.title}.",
           {"ticket_id": str(ticket.id), "entitlement_id": str(entitlement.id)},
           community_id=event.community_id, deduplication_key=f"benefit:{redemption.id}", commit=False)
    db.commit()
    return {
        "result": "redeemed",
        "entitlement": entitlement.name,
        "event": event.title,
        "ticket": ticket_type.name if ticket_type else "Ticket",
        "public_id": ticket.public_id,
        "attendee": _display_name(db, ticket.attendee_id),
        "status": state.status.value,
        "remaining": max(0, max(1, entitlement.max_redemptions_per_ticket) - state.quantity_redeemed),
        "redeemed_at": redemption.redeemed_at,
    }


def redemption_history(db: Session, event_id: UUID) -> list[dict]:
    rows = db.execute(select(EntitlementRedemption, Entitlement, Ticket).join(
        Entitlement, Entitlement.id == EntitlementRedemption.entitlement_id
    ).join(Ticket, Ticket.id == EntitlementRedemption.ticket_id).where(
        EntitlementRedemption.event_id == event_id
    ).order_by(EntitlementRedemption.created_at.desc()).limit(200)).all()
    return [{
        "id": str(redemption.id),
        "entitlement": entitlement.name,
        "ticket_public_id": ticket.public_id,
        "attendee": _display_name(db, redemption.holder_id),
        "status": redemption.status.value,
        "method": redemption.redeemed_method,
        "redeemed_at": redemption.redeemed_at,
        "expires_at": redemption.expires_at,
    } for redemption, entitlement, ticket in rows]
