"""Self check-in/out, ticket transfer, entitlement configuration, and redemption routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.config import settings
from src.database import get_db
from src.models import (
    Attendance,
    Entitlement,
    Event,
    Ticket,
    TicketType,
    User,
)
from src.schemas.attendance import AttendanceCheckIn
from src.schemas.ticket import (
    CheckInStateResponse,
    EntitlementCreate,
    EntitlementResponse,
    EntitlementUpdate,
    RedemptionIssueResponse,
    RedemptionValidateInput,
    RedemptionValidateResponse,
    TicketDetailResponse,
    TicketEntitlementResponse,
    TicketResponse,
    TransferCreateInput,
    TransferPreviewResponse,
    TransferResponse,
)
from src.services.availability import require_available
from src.services.entitlement import (
    create_entitlement,
)
from src.services.ticket import cancel_single_ticket
from src.services.ticket_attendance import (
    check_in_state,
    require_event_staff,
    self_check_in,
    self_check_out,
)
from src.services.ticket_transfer import (
    cancel_transfer,
    claim_transfer,
    create_transfer,
    transfer_preview,
)

router = APIRouter(tags=["ticketing"])


def _share_url(token: str) -> str:
    base = (settings.frontend_url or settings.canonical_url).rstrip("/")
    return f"{base}/claim/{token}"


def _owned_ticket(db: Session, ticket_id: UUID, user: User, *, lock: bool = False) -> Ticket:
    query = select(Ticket).where(Ticket.id == ticket_id)
    ticket = db.scalar(query.with_for_update()) if lock else db.scalar(query)
    if ticket is None or ticket.attendee_id != user.id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


def _event_or_404(db: Session, event_id: UUID) -> Event:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


# ── Ticket detail ────────────────────────────────────────────────────────────

@router.get("/tickets/{ticket_id}", response_model=TicketDetailResponse)
def ticket_detail(
    ticket_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    latitude: float | None = None,
    longitude: float | None = None,
    accuracy_meters: float | None = None,
):
    from src.services.entitlement import list_ticket_entitlements

    ticket = _owned_ticket(db, ticket_id, user)
    event = _event_or_404(db, ticket.event_id)
    ticket_type = db.get(TicketType, ticket.ticket_type_id)
    attendance = db.scalar(select(Attendance).where(
        Attendance.event_id == ticket.event_id, Attendance.user_id == user.id
    ))
    point = (
        AttendanceCheckIn(latitude=latitude, longitude=longitude, accuracy_meters=accuracy_meters)
        if latitude is not None and longitude is not None else None
    )
    return TicketDetailResponse(
        ticket=TicketResponse.model_validate(ticket),
        event_title=event.title,
        event_starts_at=event.starts_at,
        event_ends_at=event.ends_at,
        venue_name=event.venue.name if event.venue else None,
        venue_address=event.venue.address if event.venue else None,
        ticket_type_name=ticket_type.name if ticket_type else "Ticket",
        self_check_in_enabled=event.self_check_in_enabled,
        self_checkout_enabled=event.self_checkout_enabled,
        attendance=CheckInStateResponse(**check_in_state(db, attendance)) if attendance else None,
        entitlements=[
            TicketEntitlementResponse(**item) for item in list_ticket_entitlements(db, ticket, point=point)
        ],
    )


# ── Self check-in / checkout ─────────────────────────────────────────────────

@router.post("/events/{event_id}/tickets/{ticket_id}/check-in", response_model=CheckInStateResponse)
def ticket_self_check_in(
    event_id: UUID,
    ticket_id: UUID,
    payload: AttendanceCheckIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    return check_in_state(db, self_check_in(db, event_id, ticket_id, user, payload))


@router.post("/events/{event_id}/tickets/{ticket_id}/check-out", response_model=CheckInStateResponse)
def ticket_self_check_out(
    event_id: UUID,
    ticket_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    payload: AttendanceCheckIn | None = None,
):
    return check_in_state(db, self_check_out(db, event_id, ticket_id, user, payload))


# ── Transfer / claim ─────────────────────────────────────────────────────────

@router.post("/tickets/{ticket_id}/transfers", response_model=TransferResponse, status_code=201)
def start_transfer(
    ticket_id: UUID,
    payload: TransferCreateInput,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    ticket = _owned_ticket(db, ticket_id, user)
    transfer, token = create_transfer(db, ticket, user, recipient_email=payload.recipient_email)
    return TransferResponse(
        id=transfer.id, ticket_id=transfer.ticket_id, status=transfer.status,
        expires_at=transfer.expires_at, claimed_at=transfer.claimed_at,
        share_url=_share_url(token),
    )


@router.delete("/tickets/{ticket_id}/transfers", status_code=204)
def stop_transfer(
    ticket_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    cancel_transfer(db, _owned_ticket(db, ticket_id, user), user)


@router.get("/tickets/transfers/{token}", response_model=TransferPreviewResponse)
def preview_transfer(token: str, db: Annotated[Session, Depends(get_db)]):
    # Anonymous-safe: only the event, ticket type and link state are revealed.
    return TransferPreviewResponse(**transfer_preview(db, token))


@router.post("/tickets/transfers/{token}/claim", response_model=TicketResponse)
def claim_ticket(
    token: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    ticket = claim_transfer(db, token, user)
    return TicketResponse.model_validate(ticket)


# ── Entitlement configuration ────────────────────────────────────────────────

@router.get("/events/{event_id}/entitlements", response_model=list[EntitlementResponse])
def list_event_entitlements(
    event_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    event = _event_or_404(db, event_id)
    require_event_staff(db, event, user)
    rows = db.scalars(select(Entitlement).where(Entitlement.event_id == event_id)
                      .order_by(Entitlement.name)).all()
    return [EntitlementResponse.model_validate(row) for row in rows]


@router.post("/events/{event_id}/entitlements", response_model=EntitlementResponse, status_code=201)
def add_event_entitlement(
    event_id: UUID,
    payload: EntitlementCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    return EntitlementResponse.model_validate(
        create_entitlement(db, _event_or_404(db, event_id), payload, user)
    )


@router.patch("/events/{event_id}/entitlements/{entitlement_id}", response_model=EntitlementResponse)
def edit_event_entitlement(
    event_id: UUID,
    entitlement_id: UUID,
    payload: EntitlementUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    from src.services.entitlement import update_entitlement

    return EntitlementResponse.model_validate(
        update_entitlement(db, _event_or_404(db, event_id), db.get(Entitlement, entitlement_id), payload, user)
    )


# ── Redemption ───────────────────────────────────────────────────────────────

@router.post("/tickets/{ticket_id}/entitlements/{entitlement_id}/redemption",
             response_model=RedemptionIssueResponse)
def redeem(
    ticket_id: UUID,
    entitlement_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    payload: AttendanceCheckIn | None = None,
):
    from src.services.entitlement import redeem_entitlement

    ticket = _owned_ticket(db, ticket_id, user)
    result = redeem_entitlement(db, ticket.event_id, ticket, entitlement_id, user, point=payload)
    return RedemptionIssueResponse(**result)


@router.post("/events/{event_id}/redemptions/validate", response_model=RedemptionValidateResponse)
def validate_benefit(
    event_id: UUID,
    payload: RedemptionValidateInput,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    from src.services.entitlement import validate_redemption

    point = None
    if payload.latitude is not None and payload.longitude is not None:
        point = AttendanceCheckIn(
            latitude=payload.latitude, longitude=payload.longitude,
            accuracy_meters=payload.accuracy_meters,
        )
    return RedemptionValidateResponse(**validate_redemption(
        db, _event_or_404(db, event_id), user,
        code=payload.code, qr_payload=payload.qr_payload, point=point,
    ))


@router.get("/events/{event_id}/redemptions")
def list_redemptions(
    event_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    from src.services.entitlement import redemption_history

    event = _event_or_404(db, event_id)
    require_event_staff(db, event, user)
    return redemption_history(db, event_id)


# ── Ticket-level cancellation ────────────────────────────────────────────────

@router.post("/tickets/{ticket_id}/cancel", response_model=TicketResponse)
def cancel_one_ticket(
    ticket_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    require_available(db, db.get(Event, ticket.event_id))
    return TicketResponse.model_validate(cancel_single_ticket(db, ticket, user))
