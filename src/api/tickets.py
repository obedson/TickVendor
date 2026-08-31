"""Ticket inventory, ordering, wallet, and validation routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.database import get_db
from src.models import Ticket, User
from src.schemas.ticket import (
    OrderCreate,
    OrderResponse,
    TicketResponse,
    TicketTypeCreate,
    TicketTypeResponse,
    TicketValidationRequest,
    TicketValidationResponse,
)
from src.services.ticket import create_order, create_ticket_type, validate_ticket

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


@router.get("/tickets/me", response_model=list[TicketResponse])
def ticket_wallet(
    db: Annotated[Session, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)],
):
    return list(db.scalars(select(Ticket).where(Ticket.attendee_id == current_user.id).order_by(Ticket.created_at.desc())))


@router.post("/events/{event_id}/tickets/validate", response_model=TicketValidationResponse)
def scan_ticket(
    event_id: UUID, payload: TicketValidationRequest,
    db: Annotated[Session, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)],
):
    result, ticket = validate_ticket(db, event_id, payload.qr_token, current_user)
    return TicketValidationResponse(result=result, ticket=ticket)
