"""Public ticket inventory and purchase-support routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.auth import get_optional_user
from src.database import get_db
from src.models import (
    Event,
    Order,
    OrderStatus,
    Payment,
    Ticket,
    TicketStatus,
    TicketType,
    TicketVisibility,
    User,
)
from src.services.availability import require_available
from src.services.event import event_audience_filter
from src.services.payment import RELEASABLE_PAYMENT_STATUSES
from src.services.ticket import (
    CAPACITY_HOLDING_TICKET_STATUSES,
    expire_pending_orders,
    manage_event,
)

router = APIRouter(tags=["ticketing"])


def _maintains_event(db: Session, event: Event, user: User | None) -> bool:
    """Whether the caller maintains this event's ticket inventory, asked as a question.

    The maintainer question is the ticket module's own: ``manage_event`` is what creating and
    editing a ticket type demands, so whoever may set a type's ``visibility`` is exactly who may
    see the tiers it hides. Asking it here rather than restating it keeps one definition of that
    authority, and the refusal is read as "not a maintainer" — this only ever broadens what an
    authorized maintainer sees, since the ``False`` branch is the narrower public view.

    It is deliberately *not* the operational event-staff question. Working an event is a wider set
    than configuring its inventory: a door scanner is event staff without ever choosing what is on
    sale, and answering "yes" for every EventStaff role would hand the hidden and invite-only tiers
    to each of them by delegation. It is also why an Organizer of the community who does not own
    the event sees only public inventory — a community-wide badge is not authority over somebody
    else's event, which is the boundary the least-privilege pass drew.
    """
    if user is None:
        return False
    try:
        manage_event(db, event.id, user)
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
    # Whoever configures the inventory also sees all of it — they cannot maintain what the listing
    # hides from them; everyone else sees only what is on sale.
    conditions = [TicketType.event_id == event_id]
    if not _maintains_event(db, event, user):
        conditions.append(TicketType.visibility == TicketVisibility.PUBLIC)
    rows = db.scalars(select(TicketType).where(*conditions).order_by(TicketType.created_at)).all()
    # A reservation the caller is still holding is part of what this listing has to say: it is why
    # the number below is lower than they expect, and it is theirs to give up. Only the caller's
    # own — inventory is public information, but whose checkout is open is not — and only one whose
    # checkout can still be released, so the release this listing offers can never be refused.
    reservations: dict[UUID, dict] = {}
    if user is not None:
        held = db.execute(
            select(Ticket.ticket_type_id, Order.id, Order.expires_at, func.count(Ticket.id))
            .join(Order, Order.id == Ticket.order_id)
            .where(
                Order.user_id == user.id,
                Order.event_id == event_id,
                Order.status == OrderStatus.PENDING,
                Ticket.status == TicketStatus.PENDING_PAYMENT,
            )
            # `created_at` is grouped rather than only ordered by: PostgreSQL requires every ordered
            # expression to be grouped or aggregated, and the newest reservation per type is chosen
            # in Python below, where the first row for a type wins.
            .group_by(Ticket.ticket_type_id, Order.id, Order.expires_at, Order.created_at)
            .order_by(Order.created_at.desc())
        ).all()
        releasable = set(db.scalars(select(Payment.order_id).where(
            Payment.order_id.in_([order_id for _, order_id, _, _ in held]),
            Payment.status.in_(RELEASABLE_PAYMENT_STATUSES),
        ))) if held else set()
        for ticket_type_id, order_id, expires_at, quantity in held:
            if order_id in releasable:
                reservations.setdefault(ticket_type_id, {
                    "order_id": str(order_id),
                    "quantity": quantity,
                    "expires_at": expires_at.isoformat() if expires_at else None,
                })
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
             "sales_end": item.sales_end.isoformat() if item.sales_end else None,
             "pending_reservation": reservations.get(item.id)} for item in rows]
