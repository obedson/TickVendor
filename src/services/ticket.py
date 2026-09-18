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
    TicketAssignmentState,
    TicketStatus,
    TicketType,
    TicketVisibility,
    User,
)
from src.monitoring import emit
from src.payments.providers import PaymentProvider
from src.schemas.ticket import OrderCreate, TicketTypeCreate, TicketTypeUpdate
from src.services.event import as_utc, event_audience_filter
from src.services.notification import audit, notify

CAPACITY_HOLDING_TICKET_STATUSES = {
    TicketStatus.RESERVED,
    TicketStatus.PENDING_PAYMENT,
    TicketStatus.PAID,
    TicketStatus.ACTIVE,
    TicketStatus.USED,
}

# A free ticket type is not being sold, so one buyer has nothing legitimate to gain by sweeping the
# whole allocation in a single checkout: its per-order ceiling is one, always. That is a property
# of the price rather than a preference an organizer sets, so it is applied here rather than only
# validated at the edge — the maintenance form fixes the field, and a client that still posts a
# larger number (the shipped form default was 4) must not be able to store a ceiling that the
# purchase behind it would then have to refuse.
FREE_TICKET_MAX_PER_ORDER = 1


def per_order_ceiling(price, max_per_order: int) -> int:
    """How many tickets one order may hold, given the price the buyer pays for each."""
    return FREE_TICKET_MAX_PER_ORDER if price == 0 else max_per_order


def expire_pending_orders(
    db: Session,
    *,
    now: datetime | None = None,
    event_id: UUID | None = None,
    user_id: UUID | None = None,
) -> int:
    """Release expired paid-ticket reservations safely and idempotently.

    Locks payment before order before ticket, the order every reservation finalization takes (see
    the lock-order note in `src.services.payment`). Candidates are found unlocked and each is then
    re-read under its own lock, because a charge that confirmed while this sweep was queued has
    already turned its reservation into a sale, and that order is not this sweep's to release.
    """
    now = now or datetime.now(UTC)
    query = select(Order.id).where(
        Order.status == OrderStatus.PENDING,
        Order.expires_at.is_not(None),
        Order.expires_at <= now,
    )
    if event_id is not None:
        query = query.where(Order.event_id == event_id)
    if user_id is not None:
        query = query.where(Order.user_id == user_id)
    candidates = list(db.scalars(query))
    if not candidates:
        return 0
    expired = 0
    for order_id in candidates:
        for payment in db.scalars(select(Payment).where(
            Payment.order_id == order_id,
            Payment.status == PaymentStatus.PENDING,
        ).with_for_update()):
            payment.status = PaymentStatus.CANCELLED
            payment.failure_reason = "Ticket reservation expired before payment confirmation"
        order = db.scalar(
            select(Order)
            .where(Order.id == order_id, Order.status == OrderStatus.PENDING)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if order is None:
            continue
        order.status = OrderStatus.EXPIRED
        for ticket in db.scalars(select(Ticket).where(Ticket.order_id == order.id).with_for_update()):
            if ticket.status in {TicketStatus.RESERVED, TicketStatus.PENDING_PAYMENT}:
                ticket.status = TicketStatus.EXPIRED
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
        expired += 1
    db.commit()
    emit("ticket_reservations_expired", count=expired)
    return expired


def release_pending_order(
    db: Session,
    order: Order,
    *,
    reason: str,
    actor_id: UUID | None = None,
) -> None:
    """Cancel a pending reservation when checkout cannot be initialized.

    Locks payment before order before ticket, the same order the finalizing paths take, and re-reads
    the order under that lock: the caller hands over an order it read before locking, and by the
    time this runs the row may already have been confirmed. No payment status is changed here — a
    checkout the buyer abandoned is released by `cancel_pending_checkout` — but the lock is taken in
    the same order so this path can never be the second half of a deadlock with one that does.
    """
    db.scalars(select(Payment).where(Payment.order_id == order.id).with_for_update()).all()
    order = db.scalar(
        select(Order)
        .where(Order.id == order.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if order is None or order.status != OrderStatus.PENDING:
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
    from src.services.availability import require_available
    event = db.get(Event, event_id)
    require_available(db, event)
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
    values = payload.model_dump()
    # Normalized before the row exists, so a free type can never be stored with a ceiling larger
    # than the one purchase would honour.
    values["max_per_order"] = per_order_ceiling(payload.price, payload.max_per_order)
    model = TicketType(event_id=event_id, **values)
    db.add(model)
    db.commit()
    return model


# Fields an organizer may maintain after a ticket type exists. `event_id` is deliberately absent:
# a ticket type never moves between events, and issued tickets reference it.
EDITABLE_TICKET_TYPE_FIELDS = (
    "name", "description", "price", "currency", "quantity", "sales_start", "sales_end",
    "visibility", "max_per_user", "max_per_order",
)

# Price and currency are snapshotted on the order at purchase time, and a refund resolves the
# ticket type's live price. Changing either after tickets exist would silently restate what a
# buyer already paid, so those edits stop at the first issued ticket. New prices belong on a
# new ticket type (Early Bird / Regular are separate types in the specification).
_PRICE_LOCKED_FIELDS = ("price", "currency")


def update_ticket_type(
    db: Session, event_id: UUID, ticket_type_id: UUID, payload: TicketTypeUpdate, user: User
) -> TicketType:
    """Authorized maintenance of an existing ticket type.

    Only forward-looking configuration changes: already issued tickets, orders, payments and
    attendance are never rewritten, and inventory already committed cannot be withdrawn.
    """
    event = manage_event(db, event_id, user)
    ticket_type = db.scalar(select(TicketType).where(
        TicketType.id == ticket_type_id, TicketType.event_id == event.id
    ).with_for_update())
    if ticket_type is None:
        raise HTTPException(status_code=404, detail="Ticket type not found")
    changes = {key: value for key, value in payload.model_dump(exclude_unset=True).items()
               if key in EDITABLE_TICKET_TYPE_FIELDS}
    if not changes:
        return ticket_type

    # Resolved against the price the type will have once this edit lands, not only the one it has
    # now: a paid type that becomes free in this same payload must carry the free ceiling with it,
    # and a free type stays at one however the request words it. Assigned rather than rejected so
    # an older client posting the shipped default of 4 is corrected instead of refused.
    #
    # Compared against the value this edit would otherwise write, not against the value already
    # stored. A free type is normally stored at one already, so a stored-value comparison finds
    # nothing to correct and lets the payload's larger number through to the assignment below.
    ceiling = per_order_ceiling(
        changes.get("price", ticket_type.price),
        changes.get("max_per_order", ticket_type.max_per_order),
    )
    if changes.get("max_per_order", ticket_type.max_per_order) != ceiling:
        changes["max_per_order"] = ceiling

    issued = db.scalar(select(func.count()).select_from(Ticket).where(
        Ticket.ticket_type_id == ticket_type.id,
        Ticket.status.in_(CAPACITY_HOLDING_TICKET_STATUSES),
    )) or 0
    if any(key in changes for key in _PRICE_LOCKED_FIELDS) and issued:
        raise HTTPException(
            status_code=409,
            detail="Price and currency cannot change once tickets have been issued; create a new ticket type instead",
        )
    if "quantity" in changes and changes["quantity"] < issued:
        raise HTTPException(
            status_code=409,
            detail=f"{issued} tickets already hold this inventory; quantity cannot drop below that",
        )

    # Compare through `as_utc`: a stored window read back from SQLite is naive while a payload
    # window is timezone-aware, and the two cannot be ordered directly.
    merged_start = changes.get("sales_start", ticket_type.sales_start)
    merged_end = changes.get("sales_end", ticket_type.sales_end)
    if merged_start and merged_end and as_utc(merged_end) <= as_utc(merged_start):
        raise HTTPException(status_code=422, detail="sales_end must be after sales_start")

    for key, value in changes.items():
        setattr(ticket_type, key, value)
    audit(db, actor_id=user.id, community_id=event.community_id, action="ticket_type.updated",
          target_type="ticket_type", target_id=ticket_type.id,
          metadata={"event_id": str(event.id), "fields": sorted(changes)}, commit=False)
    db.commit()
    return ticket_type


def create_order(db: Session, event_id: UUID, payload: OrderCreate, user: User) -> Order:
    from src.services.availability import require_available
    # A private community's inventory is not purchasable by a non-member, and the check runs
    # before the idempotency replay so a returning buyer of a still-visible event is unaffected.
    event = db.scalar(select(Event).where(Event.id == event_id, event_audience_filter(user)))
    require_available(db, event)
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
    # Purchase is limited per order, never per person: one buyer may legitimately acquire many
    # tickets. How many one attendee may personally redeem is enforced at check-in instead. The
    # ceiling is resolved through the free-ticket rule rather than read raw, because this is the
    # last point that can refuse it: `max_per_order` defaults to 4 on the model itself, so a type
    # written outside this service would otherwise sell four free tickets in a single order.
    ceiling = per_order_ceiling(ticket_type.price, ticket_type.max_per_order)
    if payload.quantity > ceiling:
        raise HTTPException(
            status_code=409,
            detail=f"This ticket type allows at most {ceiling} tickets per order",
        )
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
    issued: list[Ticket] = []
    for index in range(payload.quantity):
        ticket = Ticket(
            public_id=uuid4().hex[:24].upper(), qr_token=token_urlsafe(48), event_id=event_id,
            ticket_type_id=ticket_type.id, attendee_id=user.id, purchaser_id=user.id,
            order_id=order.id,
            # The buyer keeps the first ticket for themselves; further tickets stay unassigned
            # until another attendee claims them, so one person can never redeem them all.
            assignment_state=(
                TicketAssignmentState.CLAIMED if index == 0 else TicketAssignmentState.UNASSIGNED
            ),
            status=TicketStatus.ACTIVE if is_free else TicketStatus.PENDING_PAYMENT,
        )
        db.add(ticket)
        issued.append(ticket)
    db.flush()
    from src.services.entitlement import sync_ticket_entitlements
    for ticket in issued:
        sync_ticket_entitlements(db, ticket)
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
    if ticket.assignment_state != TicketAssignmentState.CLAIMED:
        return "unassigned", ticket
    from src.services.ticket_attendance import redemption_limit_reached
    if redemption_limit_reached(db, ticket, ticket.attendee_id):
        # Server-enforced one-admission-per-attendee rule for the ticket type.
        return "duplicate_admission", ticket
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


def _recompute_order_status(db: Session, order: Order) -> None:
    """Aggregate ticket state into the order without inventing new payment transitions."""
    statuses = set(db.scalars(select(Ticket.status).where(Ticket.order_id == order.id)))
    if not statuses or not statuses.issubset(
        {TicketStatus.CANCELLED, TicketStatus.REFUNDED, TicketStatus.EXPIRED}
    ):
        return
    order.status = (
        OrderStatus.REFUNDED if TicketStatus.REFUNDED in statuses else OrderStatus.CANCELLED
    )


def cancel_single_ticket(db: Session, ticket: Ticket, user: User) -> Ticket:
    """Cancel one ticket of a multi-ticket order without touching its siblings."""
    ticket = db.scalar(select(Ticket).where(Ticket.id == ticket.id).with_for_update())
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    event = db.get(Event, ticket.event_id)
    if ticket.attendee_id != user.id and user.role != PlatformRole.SUPER_ADMIN:
        from src.services.ticket_attendance import require_event_staff
        require_event_staff(db, event, user)
    if ticket.status not in {TicketStatus.RESERVED, TicketStatus.PENDING_PAYMENT, TicketStatus.ACTIVE}:
        raise HTTPException(status_code=409, detail="Ticket cannot be cancelled")
    ticket.status = TicketStatus.CANCELLED
    order = db.get(Order, ticket.order_id) if ticket.order_id else None
    if order is not None:
        _recompute_order_status(db, order)
    audit(db, actor_id=user.id, community_id=event.community_id if event else None,
          action="ticket.cancelled", target_type="ticket", target_id=ticket.id,
          metadata={"order_id": str(order.id) if order else None}, commit=False)
    db.commit()
    return ticket


def refund_single_ticket(
    db: Session, ticket: Ticket, user: User, provider: PaymentProvider
) -> tuple[Ticket, bool]:
    """Refund one ticket of a multi-ticket order; sibling tickets are unaffected.

    Returns ``(ticket, completed)``. ``completed`` is False while the provider reports a
    pending refund; the ticket stays valid until the provider settles.
    """
    ticket = db.scalar(select(Ticket).where(Ticket.id == ticket.id).with_for_update())
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.attendee_id != user.id and user.role != PlatformRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Ticket ownership required")
    if ticket.status == TicketStatus.REFUNDED:
        raise HTTPException(status_code=409, detail="This ticket is already refunded")
    if ticket.status not in {TicketStatus.ACTIVE, TicketStatus.PENDING_PAYMENT, TicketStatus.RESERVED}:
        raise HTTPException(status_code=409, detail="Ticket cannot be refunded")
    if ticket.used_at is not None:
        raise HTTPException(status_code=409, detail="A checked-in ticket cannot be refunded automatically")
    order = db.get(Order, ticket.order_id) if ticket.order_id else None
    event = db.get(Event, ticket.event_id)
    payment = None
    if ticket.order_id is not None:
        payment = db.scalar(select(Payment).where(
            Payment.order_id == ticket.order_id, Payment.status == PaymentStatus.SUCCESSFUL,
        ))
    if payment is not None:
        metadata = dict(payment.provider_metadata or {})
        refunds = dict(metadata.get("ticket_refunds") or {})
        key = str(ticket.id)
        if key not in refunds:
            try:
                result = provider.refund(payment.provider_reference, ticket_type_price(db, ticket))
            except Exception as exc:
                emit("payment_refund_failure", provider=payment.provider,
                     payment_id=str(payment.id), error_type=type(exc).__name__)
                payment.failure_reason = f"Refund initiation failed: {type(exc).__name__}"
                db.commit()
                raise HTTPException(status_code=502, detail="Payment provider refund failed") from exc
            refunds[key] = {
                "reference": str(result.get("reference", payment.provider_reference)),
                "status": str(result.get("status", "pending")),
            }
            metadata["ticket_refunds"] = refunds
            metadata["refund_status"] = refunds[key]["status"]
            payment.provider_metadata = metadata
        if refunds.get(key, {}).get("status") != "success":
            db.commit()
            return ticket, False
    ticket.status = TicketStatus.REFUNDED
    if order is not None:
        _recompute_order_status(db, order)
    audit(db, actor_id=user.id, community_id=event.community_id if event else None,
          action="ticket.refunded", target_type="ticket", target_id=ticket.id,
          metadata={"order_id": str(order.id) if order else None}, commit=False)
    db.commit()
    return ticket, True


def ticket_type_price(db: Session, ticket: Ticket):
    ticket_type = db.get(TicketType, ticket.ticket_type_id)
    return ticket_type.price if ticket_type else 0


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
