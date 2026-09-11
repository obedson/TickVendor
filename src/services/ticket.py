"""Ticket inventory, order, issuance, wallet, and atomic validation services."""

from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.authorization import require_community_role
from src.models import (
    Event,
    EventStaff,
    EventStatus,
    MembershipRole,
    Order,
    OrderStatus,
    Payment,
    PaymentStatus,
    PlatformRole,
    Ticket,
    TicketStatus,
    TicketType,
    TicketVisibility,
    User,
)
from src.monitoring import emit
from src.payments.providers import PaymentProvider
from src.schemas.ticket import OrderCreate, TicketTypeCreate
from src.services.event import as_utc
from src.services.notification import audit, notify

CAPACITY_HOLDING_TICKET_STATUSES = {
    TicketStatus.RESERVED,
    TicketStatus.PENDING_PAYMENT,
    TicketStatus.PAID,
    TicketStatus.ACTIVE,
    TicketStatus.USED,
}


def expire_pending_orders(
    db: Session,
    *,
    now: datetime | None = None,
    event_id: UUID | None = None,
    user_id: UUID | None = None,
) -> int:
    """Release expired paid-ticket reservations safely and idempotently."""
    now = now or datetime.now(UTC)
    query = select(Order).where(
        Order.status == OrderStatus.PENDING,
        Order.expires_at.is_not(None),
        Order.expires_at <= now,
    )
    if event_id is not None:
        query = query.where(Order.event_id == event_id)
    if user_id is not None:
        query = query.where(Order.user_id == user_id)
    orders = list(db.scalars(query.with_for_update()))
    if not orders:
        return 0
    for order in orders:
        order.status = OrderStatus.EXPIRED
        for ticket in db.scalars(select(Ticket).where(Ticket.order_id == order.id).with_for_update()):
            if ticket.status in {TicketStatus.RESERVED, TicketStatus.PENDING_PAYMENT}:
                ticket.status = TicketStatus.EXPIRED
        for payment in db.scalars(select(Payment).where(
            Payment.order_id == order.id,
            Payment.status == PaymentStatus.PENDING,
        ).with_for_update()):
            payment.status = PaymentStatus.CANCELLED
            payment.failure_reason = "Ticket reservation expired before payment confirmation"
        event = db.get(Event, order.event_id)
        audit(
            db,
            actor_id=None,
            community_id=event.community_id if event else None,
            action="order.expired",
            target_type="order",
            target_id=order.id,
            metadata={"reason": "payment_reservation_timeout"},
            commit=False,
        )
    db.commit()
    emit("ticket_reservations_expired", count=len(orders))
    return len(orders)


def release_pending_order(
    db: Session,
    order: Order,
    *,
    reason: str,
    actor_id: UUID | None = None,
) -> None:
    """Cancel a pending reservation when checkout cannot be initialized."""
    if order.status != OrderStatus.PENDING:
        return
    order.status = OrderStatus.CANCELLED
    for ticket in db.scalars(select(Ticket).where(Ticket.order_id == order.id).with_for_update()):
        if ticket.status in {TicketStatus.RESERVED, TicketStatus.PENDING_PAYMENT}:
            ticket.status = TicketStatus.CANCELLED
    event = db.get(Event, order.event_id)
    audit(
        db,
        actor_id=actor_id,
        community_id=event.community_id if event else None,
        action="order.cancelled",
        target_type="order",
        target_id=order.id,
        metadata={"reason": reason},
        commit=False,
    )
    db.commit()


def manage_event(db: Session, event_id: UUID, user: User) -> Event:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    membership = require_community_role(db, event.community_id, user, MembershipRole.ORGANIZER)
    if user.role != PlatformRole.SUPER_ADMIN and membership.role != MembershipRole.ADMIN and event.organizer_id != user.id:
        raise HTTPException(status_code=403, detail="Event ownership required")
    return event


def create_ticket_type(db: Session, event_id: UUID, payload: TicketTypeCreate, user: User) -> TicketType:
    manage_event(db, event_id, user)
    if payload.sales_start and payload.sales_end and payload.sales_end <= payload.sales_start:
        raise HTTPException(status_code=422, detail="sales_end must be after sales_start")
    model = TicketType(event_id=event_id, **payload.model_dump())
    db.add(model)
    db.commit()
    return model


def create_order(db: Session, event_id: UUID, payload: OrderCreate, user: User) -> Order:
    expire_pending_orders(db, event_id=event_id)
    existing = db.scalar(select(Order).where(Order.idempotency_key == payload.idempotency_key))
    if existing:
        if existing.user_id != user.id or existing.event_id != event_id:
            raise HTTPException(status_code=409, detail="Idempotency key conflict")
        existing_tickets = list(db.scalars(select(Ticket).where(Ticket.order_id == existing.id)))
        if (len(existing_tickets) != payload.quantity
                or any(ticket.ticket_type_id != payload.ticket_type_id for ticket in existing_tickets)):
            raise HTTPException(status_code=409, detail="Idempotency key conflict")
        return existing
    event = db.get(Event, event_id)
    ticket_type = db.scalar(select(TicketType).where(
        TicketType.id == payload.ticket_type_id
    ).with_for_update())
    now = datetime.now(UTC)
    if event is None or event.status != EventStatus.PUBLISHED:
        raise HTTPException(status_code=404, detail="Published event not found")
    if ticket_type is None or ticket_type.event_id != event_id:
        raise HTTPException(status_code=404, detail="Ticket type not found")
    if ticket_type.visibility != TicketVisibility.PUBLIC:
        raise HTTPException(status_code=403, detail="Ticket type is not publicly available")
    if ticket_type.sales_start and as_utc(ticket_type.sales_start) > now:
        raise HTTPException(status_code=409, detail="Ticket sales have not started")
    if ticket_type.sales_end and as_utc(ticket_type.sales_end) < now:
        raise HTTPException(status_code=409, detail="Ticket sales have ended")
    active_reservation = db.scalar(
        select(Order)
        .join(Ticket, Ticket.order_id == Order.id)
        .where(
            Order.user_id == user.id,
            Order.event_id == event_id,
            Order.status == OrderStatus.PENDING,
            Ticket.ticket_type_id == ticket_type.id,
            Ticket.status == TicketStatus.PENDING_PAYMENT,
        )
        .order_by(Order.created_at.desc())
    )
    if active_reservation is not None:
        return active_reservation
    issued = db.scalar(select(func.count()).select_from(Ticket).where(
        Ticket.ticket_type_id == ticket_type.id,
        Ticket.status.in_(CAPACITY_HOLDING_TICKET_STATUSES),
    )) or 0
    if issued + payload.quantity > ticket_type.quantity:
        raise HTTPException(status_code=409, detail="Insufficient ticket inventory")
    owned = db.scalar(select(func.count()).select_from(Ticket).where(
        Ticket.ticket_type_id == ticket_type.id, Ticket.attendee_id == user.id,
        Ticket.status.notin_([TicketStatus.CANCELLED, TicketStatus.REFUNDED, TicketStatus.EXPIRED]),
    )) or 0
    if owned + payload.quantity > ticket_type.max_per_user:
        raise HTTPException(status_code=409, detail="Maximum tickets per user exceeded")
    is_free = ticket_type.price == 0
    order = Order(
        reference=f"TE-{uuid4().hex[:20].upper()}", idempotency_key=payload.idempotency_key,
        user_id=user.id, event_id=event_id,
        status=OrderStatus.CONFIRMED if is_free else OrderStatus.PENDING,
        total_amount=ticket_type.price * payload.quantity, currency=ticket_type.currency,
        expires_at=None if is_free else now + timedelta(minutes=15),
    )
    db.add(order)
    db.flush()
    for _ in range(payload.quantity):
        db.add(Ticket(
            public_id=uuid4().hex[:24].upper(), qr_token=token_urlsafe(48), event_id=event_id,
            ticket_type_id=ticket_type.id, attendee_id=user.id, order_id=order.id,
            status=TicketStatus.ACTIVE if is_free else TicketStatus.PENDING_PAYMENT,
        ))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent order conflict; retry safely") from exc
    if is_free:
        notify(db, user.id, "ticket_confirmed", "Ticket confirmed",
               "Your ticket has been confirmed.", {"event_id": str(event_id), "order_id": str(order.id)},
               community_id=event.community_id)
    return order


def validate_ticket(db: Session, event_id: UUID, qr_token: str, staff: User) -> tuple[str, Ticket | None]:
    event = manage_event(db, event_id, staff)
    authorized_staff = db.scalar(select(EventStaff.id).where(
        EventStaff.event_id == event_id, EventStaff.user_id == staff.id, EventStaff.is_active.is_(True)
    ))
    if staff.role != PlatformRole.SUPER_ADMIN and event.organizer_id != staff.id and authorized_staff is None:
        membership = require_community_role(db, event.community_id, staff, MembershipRole.ADMIN)
        if membership.role != MembershipRole.ADMIN:
            raise HTTPException(status_code=403, detail="Ticket validation permission required")
    ticket = db.scalar(select(Ticket).where(Ticket.qr_token == qr_token).with_for_update())
    if ticket is None:
        return "invalid", None
    if ticket.event_id != event_id:
        return "wrong_event", None
    if ticket.status == TicketStatus.USED:
        return "already_used", ticket
    if ticket.status != TicketStatus.ACTIVE:
        return "invalid_status", ticket
    attendance = None
    qr_added = False
    if event.qr_attendance_enabled:
        from src.services.attendance import record_qr_attendance

        attendance, qr_added = record_qr_attendance(db, event, ticket, staff)
    ticket.status = TicketStatus.USED
    ticket.used_at = datetime.now(UTC)
    ticket.validated_by_id = staff.id
    db.commit()
    if attendance is not None and qr_added:
        from src.services.attendance import (
            award_qualified_attendance,
            calculate_attendance_confidence,
        )

        calculate_attendance_confidence(db, attendance)
        award_qualified_attendance(db, attendance)
        audit(db, actor_id=staff.id, community_id=event.community_id,
              action="attendance.verified", target_type="attendance", target_id=attendance.id,
              metadata={"event_id": str(event_id), "method": "qr"})
    audit(db, actor_id=staff.id, community_id=event.community_id, action="ticket.used",
          target_type="ticket", target_id=ticket.id, metadata={"event_id": str(event_id)})
    return "valid", ticket


def cancel_ticket(db: Session, ticket: Ticket, user: User) -> Ticket:
    if ticket.attendee_id != user.id and user.role != PlatformRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Ticket ownership required")
    if ticket.status not in {TicketStatus.RESERVED, TicketStatus.PENDING_PAYMENT, TicketStatus.ACTIVE}:
        raise HTTPException(status_code=409, detail="Ticket cannot be cancelled")
    ticket.status = TicketStatus.CANCELLED
    db.commit()
    event = db.get(Event, ticket.event_id)
    audit(db, actor_id=user.id, community_id=event.community_id, action="ticket.cancelled",
          target_type="ticket", target_id=ticket.id)
    return ticket


def refund_order(db: Session, order: Order, user: User, provider: PaymentProvider) -> Order:
    if order.user_id != user.id and user.role != PlatformRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Order ownership required")
    if order.status not in {OrderStatus.CONFIRMED, OrderStatus.PENDING}:
        raise HTTPException(status_code=409, detail="Order cannot be refunded")
    payment = db.scalar(select(Payment).where(
        Payment.order_id == order.id, Payment.status == PaymentStatus.SUCCESSFUL,
    ))
    if payment is not None:
        metadata = dict(payment.provider_metadata or {})
        if not metadata.get("refund_reference"):
            try:
                result = provider.refund(payment.provider_reference, payment.amount)
            except Exception as exc:
                emit("payment_refund_failure", provider=payment.provider,
                     payment_id=str(payment.id), error_type=type(exc).__name__)
                payment.failure_reason = f"Refund initiation failed: {type(exc).__name__}"
                db.commit()
                raise HTTPException(status_code=502, detail="Payment provider refund failed") from exc
            metadata["refund_reference"] = str(result.get("reference", payment.provider_reference))
            metadata["refund_status"] = str(result.get("status", "pending"))
            payment.provider_metadata = metadata
        if metadata.get("refund_status") != "success":
            db.commit()
            return order
        payment.status = PaymentStatus.REFUNDED
        payment.refunded_at = datetime.now(UTC)
    order.status = OrderStatus.REFUNDED
    for ticket in db.scalars(select(Ticket).where(Ticket.order_id == order.id)):
        if ticket.status != TicketStatus.USED:
            ticket.status = TicketStatus.REFUNDED
    db.commit()
    event = db.get(Event, order.event_id)
    audit(db, actor_id=user.id, community_id=event.community_id, action="order.refunded",
          target_type="order", target_id=order.id)
    return order
