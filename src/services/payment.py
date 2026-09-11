"""Payment initialization and idempotent verification service."""

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models import (
    Event,
    Order,
    OrderStatus,
    Payment,
    PaymentStatus,
    PlatformRole,
    Ticket,
    TicketStatus,
    User,
)
from src.monitoring import emit
from src.payments.providers import PaymentProvider
from src.services.notification import audit, notify
from src.services.ticket import release_pending_order


def initialize_payment(db: Session, order: Order, user_email: str, idempotency_key: str, provider: PaymentProvider):
    existing = db.scalar(select(Payment).where(Payment.idempotency_key == idempotency_key))
    if existing:
        if (existing.order_id != order.id or existing.provider != provider.name
                or existing.amount != order.total_amount or existing.currency != order.currency):
            raise HTTPException(status_code=409, detail="Payment idempotency key conflict")
        checkout_url = str(existing.provider_metadata.get("checkout_url", ""))
        if not checkout_url:
            raise HTTPException(status_code=409, detail="Original payment checkout is unavailable")
        from src.payments.providers import PaymentInitialization
        return existing, PaymentInitialization(existing.provider_reference, checkout_url)
    if order.status != OrderStatus.PENDING or order.total_amount <= 0:
        raise HTTPException(status_code=409, detail="Order is not payable")
    try:
        initialization = provider.initialize(
            order.reference, order.total_amount, order.currency, user_email
        )
    except Exception as exc:
        emit(
            "payment_initialization_failure",
            provider=provider.name,
            order_id=str(order.id),
            error_type=type(exc).__name__,
        )
        release_pending_order(
            db, order, reason="payment_provider_initialization_failed", actor_id=order.user_id
        )
        raise HTTPException(
            status_code=502,
            detail="Payment checkout could not be started. Your ticket reservation was released; please try again.",
        ) from exc
    if initialization.provider_reference != order.reference or not initialization.checkout_url.startswith(("https://", "http://")):
        release_pending_order(
            db, order, reason="invalid_payment_provider_initialization", actor_id=order.user_id
        )
        raise HTTPException(
            status_code=502,
            detail="Payment provider returned an invalid checkout response. Your ticket reservation was released.",
        )
    payment = Payment(
        order_id=order.id, provider=provider.name,
        provider_reference=initialization.provider_reference,
        idempotency_key=idempotency_key, amount=order.total_amount, currency=order.currency,
        provider_metadata={"checkout_url": initialization.checkout_url},
    )
    db.add(payment)
    db.commit()
    return payment, initialization


def apply_successful_payment(db: Session, payment: Payment, provider: PaymentProvider) -> Payment:
    payment = db.scalar(
        select(Payment)
        .where(Payment.id == payment.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if payment.status == PaymentStatus.SUCCESSFUL:
        return payment
    try:
        verification = provider.verify(payment.provider_reference)
    except Exception as exc:
        emit(
            "payment_verification_failure",
            provider=provider.name,
            payment_id=str(payment.id),
            error_type=type(exc).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail="Payment provider verification is temporarily unavailable. Please try again.",
        ) from exc
    if not verification.successful:
        if verification.status in {"failed", "abandoned", "cancelled", "reversed"}:
            payment.status = PaymentStatus.FAILED
            payment.failure_reason = f"Provider reported {verification.status}"
            db.commit()
        raise HTTPException(status_code=409, detail="Payment status is not successful")
    order = db.scalar(
        select(Order)
        .where(Order.id == payment.order_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if order is None:
        raise HTTPException(status_code=409, detail="Payment order is unavailable")
    if verification.provider_reference != payment.provider_reference:
        raise HTTPException(status_code=409, detail="Payment reference mismatch")
    if verification.amount != payment.amount or verification.amount != order.total_amount:
        raise HTTPException(status_code=409, detail="Payment amount mismatch")
    if verification.currency != payment.currency or verification.currency != order.currency:
        raise HTTPException(status_code=409, detail="Payment currency mismatch")
    if order.status not in {OrderStatus.PENDING, OrderStatus.CONFIRMED}:
        payment.status = PaymentStatus.SUCCESSFUL
        payment.verified_at = datetime.now(UTC)
        payment.failure_reason = "Payment confirmed after ticket reservation ended; refund review required"
        event = db.get(Event, order.event_id)
        audit(
            db,
            actor_id=order.user_id,
            community_id=event.community_id if event else None,
            action="payment.late_confirmation",
            target_type="payment",
            target_id=payment.id,
            metadata={"order_status": order.status.value},
            commit=False,
        )
        db.commit()
        raise HTTPException(
            status_code=409,
            detail="Payment was confirmed after the reservation ended. No ticket was activated; contact support for refund review.",
        )
    first_confirmation = order.status == OrderStatus.PENDING
    payment.status = PaymentStatus.SUCCESSFUL
    payment.verified_at = datetime.now(UTC)
    order.status = OrderStatus.CONFIRMED
    for ticket in db.scalars(select(Ticket).where(Ticket.order_id == order.id).with_for_update()):
        if ticket.status == TicketStatus.PENDING_PAYMENT:
            ticket.status = TicketStatus.ACTIVE
    if first_confirmation:
        event = db.get(Event, order.event_id)
        audit(
            db,
            actor_id=order.user_id,
            community_id=event.community_id if event else None,
            action="payment.verified",
            target_type="payment",
            target_id=payment.id,
            metadata={"order_id": str(order.id), "provider": payment.provider},
            commit=False,
        )
        notify(
            db,
            order.user_id,
            "ticket_confirmed",
            "Ticket confirmed",
            "Your payment was verified and your ticket is now active.",
            {"event_id": str(order.event_id), "order_id": str(order.id)},
            community_id=event.community_id if event else None,
            deduplication_key=f"paid-ticket-confirmed:{order.id}",
            commit=False,
        )
    db.commit()
    return payment


def reconcile_payment(
    db: Session, payment: Payment, provider: PaymentProvider, actor: User
) -> dict[str, object]:
    """Compare local/provider payment data and audit; never silently correct state."""
    order = db.get(Order, payment.order_id)
    if order is None or (order.user_id != actor.id and actor.role != PlatformRole.SUPER_ADMIN):
        raise HTTPException(status_code=404, detail="Payment not found")
    verification = provider.verify(payment.provider_reference)
    mismatches: list[str] = []
    if verification.provider_reference != payment.provider_reference:
        mismatches.append("reference")
    if verification.amount != payment.amount:
        mismatches.append("amount")
    if verification.currency != payment.currency:
        mismatches.append("currency")
    expected = "success" if payment.status == PaymentStatus.SUCCESSFUL else payment.status.value
    if verification.status != expected:
        mismatches.append("status")
    result: dict[str, object] = {
        "payment_id": str(payment.id), "provider_status": verification.status,
        "local_status": payment.status.value, "mismatches": mismatches,
    }
    event = db.get(Event, order.event_id)
    audit(db, actor_id=actor.id, community_id=event.community_id,
          action="payment.reconciled", target_type="payment", target_id=payment.id,
          metadata=result)
    return result
