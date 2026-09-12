"""Owned, typed and reversible presentation preferences."""
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select

from src.models import (
    ActivityOpportunity,
    Event,
    Notification,
    OpportunityRegistration,
    Order,
    OrderStatus,
    PersonalArchive,
    Task,
    TaskAssignment,
    Ticket,
    TicketStatus,
    User,
)

MODELS = {"notification": (Notification, "user_id"), "ticket": (Ticket, "attendee_id"),
          "task": (TaskAssignment, "assignee_id"), "opportunity": (OpportunityRegistration, "participant_id")}


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def eligible(db, kind, item):
    if kind == "notification":
        return True
    if kind == "ticket":
        event = db.get(Event, item.event_id)
        return item.status in {TicketStatus.USED, TicketStatus.CANCELLED, TicketStatus.REFUNDED, TicketStatus.EXPIRED} or utc(event.ends_at) < datetime.now(UTC)
    if kind == "task":
        return item.status.value in {"completed", "verified"}
    opportunity = db.get(ActivityOpportunity, item.opportunity_id)
    return item.status.value in {"completed", "verified", "rejected"} or opportunity.status.value in {"closed", "cancelled"} or utc(opportunity.ends_at) < datetime.now(UTC)


def issued_ticket(db, item):
    if item.status in {TicketStatus.RESERVED, TicketStatus.PENDING_PAYMENT}:
        return False
    order = db.get(Order, item.order_id) if item.order_id else None
    return not item.order_id or order is not None and order.status in {OrderStatus.CONFIRMED, OrderStatus.REFUNDED}


def set_archive(db, user, kind, item_id, archived):
    # Serializes concurrent preferences for this user; unique key is the final guard.
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    model, owner = MODELS[kind]
    item = db.get(model, item_id)
    if item is None or getattr(item, owner) != user.id or kind == "ticket" and not issued_ticket(db, item):
        raise HTTPException(404, "Personal item not found")
    preference = db.scalar(select(PersonalArchive).where(PersonalArchive.user_id == user.id,
        PersonalArchive.item_type == kind, PersonalArchive.item_id == item_id))
    if archived:
        if not eligible(db, kind, item):
            raise HTTPException(409, "Only historical or completed records may be archived")
        if preference is None:
            db.add(PersonalArchive(user_id=user.id, item_type=kind, item_id=item_id, archived_at=datetime.now(UTC)))
    elif preference is not None:
        db.delete(preference)  # Only the presentation preference; never evidence.
    db.commit()


def personal_items(db, user, kind, offset):
    model, owner = MODELS[kind]
    query = select(model).where(getattr(model, owner) == user.id)
    if kind == "ticket":
        query = query.outerjoin(Order, Order.id == Ticket.order_id).where(
            Ticket.status.notin_([TicketStatus.RESERVED, TicketStatus.PENDING_PAYMENT]),
            (Ticket.order_id.is_(None) | Order.status.in_([OrderStatus.CONFIRMED, OrderStatus.REFUNDED])))
    items = db.scalars(query.order_by(model.created_at.desc(), model.id).offset(offset).limit(50))
    archived = set(db.scalars(select(PersonalArchive.item_id).where(PersonalArchive.user_id == user.id, PersonalArchive.item_type == kind)))
    result = []
    for item in items:
        parent = db.get(Event, item.event_id) if kind == "ticket" else db.get(Task, item.task_id) if kind == "task" else db.get(ActivityOpportunity, item.opportunity_id) if kind == "opportunity" else item
        result.append({"id": str(item.id), "title": parent.title, "status": item.status.value if hasattr(item, "status") else "read" if item.read_at else "unread",
                       "archived": item.id in archived, "eligible": eligible(db, kind, item), "created_at": item.created_at})
    return result
