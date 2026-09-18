"""Public ticket inventory and purchase-support routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.auth import get_optional_user
from src.database import get_db
from src.models import Event, Ticket, TicketStatus, TicketType, TicketVisibility, User
from src.services.availability import require_available
from src.services.event import event_audience_filter
from src.services.ticket import CAPACITY_HOLDING_TICKET_STATUSES, expire_pending_orders
from src.services.ticket_attendance import require_event_staff

router = APIRouter(tags=["ticketing"])


def _maintains_event(db: Session, event: Event, user: User | None) -> bool:
    """Whether the caller maintains this event, asked as a question rather than a demand.

    ``require_event_staff`` is the single authority on what "event staff" means; restating its
    rules here would give the codebase a second copy to drift out of step. So its refusal is read
    as "not staff". This only ever broadens what an authorized maintainer sees — the ``False``
    branch is the narrower public view.
    """
    if user is None:
        return False
    try:
        require_event_staff(db, event, user)
    except HTTPException:
        return False
    return True


@router.get("/events/{event_id}/ticket-types")
def list_event_ticket_types(
    event_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User | None, Depends(get_optional_user)],
):
    expire_pending_orders(db, event_id=event_id)
    # Prices are event information: a private community's inventory is not readable by a
    # non-member even though they are signed in. A public community's inventory is readable by
    # anyone — including a signed-out guest deciding whether the event is worth an account — so
    # the audience condition, not authentication, is what decides this. `require_available` still
    # reports a suspended event as forbidden, so only the audience condition is added here.
    event = db.scalar(select(Event).where(
        Event.id == event_id, event_audience_filter(user)
    ))
    require_available(db, event)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    # An organizer maintains hidden and invite-only tiers as well, and cannot maintain what the
    # listing hides from them; everyone else sees only what is on sale.
    conditions = [TicketType.event_id == event_id]
    if not _maintains_event(db, event, user):
        conditions.append(TicketType.visibility == TicketVisibility.PUBLIC)
    rows = db.scalars(select(TicketType).where(*conditions).order_by(TicketType.created_at)).all()
    return [{"id": str(item.id), "event_id": str(item.event_id), "name": item.name, "description": item.description,
             "price": str(item.price), "currency": item.currency, "quantity": item.quantity,
             "sold": db.scalar(select(func.count()).select_from(Ticket).where(Ticket.ticket_type_id == item.id,
                 Ticket.status.notin_([TicketStatus.CANCELLED, TicketStatus.REFUNDED, TicketStatus.EXPIRED]))) or 0,
             "availability": max(0, item.quantity - (db.scalar(select(func.count()).select_from(Ticket).where(
                 Ticket.ticket_type_id == item.id,
                 Ticket.status.in_(CAPACITY_HOLDING_TICKET_STATUSES))) or 0)),
             "visibility": item.visibility.value, "max_per_user": item.max_per_user,
             # A buyer choosing a quantity needs the organizer's own per-order ceiling and the
             # sales window, and the organizer's editor maintains both, so they are reported
             # rather than left for the client to guess at.
             "max_per_order": item.max_per_order,
             "sales_start": item.sales_start.isoformat() if item.sales_start else None,
             "sales_end": item.sales_end.isoformat() if item.sales_end else None} for item in rows]
