"""Ticket inventory, ordering, wallet, and validation routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.database import get_db
from src.models import Event, Order, OrderStatus, Ticket, TicketStatus, TicketType, User
from src.schemas.ticket import (
    OrderCreate,
    OrderResponse,
    TicketTypeCreate,
    TicketTypeResponse,
    TicketValidationRequest,
    TicketValidationResponse,
    TicketWalletResponse,
)
from src.services.ticket import (
    create_order,
    create_ticket_type,
    expire_pending_orders,
    validate_ticket,
)

router = APIRouter(tags=["ticketing"])


@router.post("/events/{event_id}/ticket-types", response_model=TicketTypeResponse, status_code=201)
def add_ticket_type(
    event_id: UUID, payload: TicketTypeCreate,
    db: Annotated[Session, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)],
):
    return create_ticket_type(db, event_id, payload, current_user)


@router.post("/events/{event_id}/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def order_tickets(
    event_id: UUID, payload: OrderCreate,
    db: Annotated[Session, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)],
):
    return create_order(db, event_id, payload, current_user)


@router.get("/tickets/me", response_model=list[TicketWalletResponse])
def ticket_wallet(
    db: Annotated[Session, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)],
):
    expire_pending_orders(db, user_id=current_user.id)
    rows = db.execute(select(Ticket, Event, TicketType).join(Event, Event.id == Ticket.event_id)
                      .join(TicketType, TicketType.id == Ticket.ticket_type_id)
                      .outerjoin(Order, Order.id == Ticket.order_id)
                      .where(
                          Ticket.attendee_id == current_user.id,
                          Ticket.status.notin_([TicketStatus.RESERVED, TicketStatus.PENDING_PAYMENT]),
                          or_(
                              Ticket.order_id.is_(None),
                              Order.status.in_([OrderStatus.CONFIRMED, OrderStatus.REFUNDED]),
                          ),
                      )
                      .order_by(Ticket.created_at.desc()))
    result = []
    for ticket, event, ticket_type in rows:
        group = "cancelled" if ticket.status in {
            TicketStatus.CANCELLED, TicketStatus.REFUNDED, TicketStatus.EXPIRED,
        } else "used" if ticket.status == TicketStatus.USED else "upcoming"
        result.append(TicketWalletResponse.model_validate({
            **{key: getattr(ticket, key) for key in ("id", "public_id", "qr_token", "event_id", "ticket_type_id", "attendee_id", "order_id", "status", "used_at")},
            "event_title": event.title, "event_starts_at": event.starts_at,
            "event_ends_at": event.ends_at,
            "venue_name": event.venue.name if event.venue else None,
            "venue_address": event.venue.address if event.venue else None,
            "ticket_type_name": ticket_type.name, "group": group,
        }))
    return result


@router.post("/events/{event_id}/tickets/validate", response_model=TicketValidationResponse)
def scan_ticket(
    event_id: UUID, payload: TicketValidationRequest,
    db: Annotated[Session, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)],
):
    result, ticket = validate_ticket(db, event_id, payload.qr_token, current_user)
    return TicketValidationResponse(result=result, ticket=ticket)
