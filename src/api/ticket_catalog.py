"""Public ticket inventory and purchase-support routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.database import get_db
from src.models import Event, Ticket, TicketStatus, TicketType, TicketVisibility, User

router = APIRouter(tags=["ticketing"])


@router.get("/events/{event_id}/ticket-types")
def list_event_ticket_types(event_id: UUID, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    event = db.scalar(select(Event).where(Event.id == event_id))
    if event is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Event not found")
    rows = db.scalars(select(TicketType).where(TicketType.event_id == event_id, TicketType.visibility == TicketVisibility.PUBLIC).order_by(TicketType.created_at)).all()
    return [{"id": str(item.id), "event_id": str(item.event_id), "name": item.name, "description": item.description,
             "price": str(item.price), "currency": item.currency, "quantity": item.quantity,
             "sold": db.scalar(select(func.count()).select_from(Ticket).where(Ticket.ticket_type_id == item.id,
                 Ticket.status.notin_([TicketStatus.CANCELLED, TicketStatus.REFUNDED, TicketStatus.EXPIRED]))) or 0,
             "availability": max(0, item.quantity - (db.scalar(select(func.count()).select_from(Ticket).where(Ticket.ticket_type_id == item.id)) or 0)),
             "visibility": item.visibility.value, "max_per_user": item.max_per_user} for item in rows]
