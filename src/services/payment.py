"""Payment initialization and idempotent verification service."""

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models import Order, OrderStatus, Payment, PaymentStatus, Ticket, TicketStatus
from src.payments.providers import PaymentProvider


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
    initialization = provider.initialize(order.reference, order.total_amount, order.currency, user_email)
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
    if payment.status == PaymentStatus.SUCCESSFUL:
        return payment
    verification = provider.verify(payment.provider_reference)
    if not verification.successful:
        payment.status = PaymentStatus.FAILED
        payment.failure_reason = "Provider verification failed"
        db.commit()
        raise HTTPException(status_code=409, detail="Payment status is not successful")
    order = db.get(Order, payment.order_id)
    if verification.provider_reference != payment.provider_reference:
        raise HTTPException(status_code=409, detail="Payment reference mismatch")
    if verification.amount != payment.amount or verification.amount != order.total_amount:
        raise HTTPException(status_code=409, detail="Payment amount mismatch")
    if verification.currency != payment.currency or verification.currency != order.currency:
        raise HTTPException(status_code=409, detail="Payment currency mismatch")
    payment.status = PaymentStatus.SUCCESSFUL
    payment.verified_at = datetime.now(UTC)
    order.status = OrderStatus.CONFIRMED
    for ticket in db.scalars(select(Ticket).where(Ticket.order_id == order.id).with_for_update()):
        if ticket.status == TicketStatus.PENDING_PAYMENT:
            ticket.status = TicketStatus.ACTIVE
    db.commit()
    return payment
