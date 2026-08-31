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
        return existing, provider.initialize(
            existing.provider_reference, existing.amount, existing.currency, user_email
        )
    if order.status != OrderStatus.PENDING or order.total_amount <= 0:
        raise HTTPException(status_code=409, detail="Order is not payable")
    initialization = provider.initialize(order.reference, order.total_amount, order.currency, user_email)
    payment = Payment(
        order_id=order.id, provider=provider.name,
        provider_reference=initialization.provider_reference,
        idempotency_key=idempotency_key, amount=order.total_amount, currency=order.currency,
    )
    db.add(payment)
    db.commit()
    return payment, initialization


def apply_successful_payment(db: Session, payment: Payment, provider: PaymentProvider) -> Payment:
    if payment.status == PaymentStatus.SUCCESSFUL:
        return payment
    if not provider.verify(payment.provider_reference):
        payment.status = PaymentStatus.FAILED
        payment.failure_reason = "Provider verification failed"
        db.commit()
        raise HTTPException(status_code=409, detail="Payment could not be verified")
    order = db.get(Order, payment.order_id)
    if order is None or payment.amount != order.total_amount or payment.currency != order.currency:
        raise HTTPException(status_code=409, detail="Payment amount or currency mismatch")
    payment.status = PaymentStatus.SUCCESSFUL
    payment.verified_at = datetime.now(UTC)
    order.status = OrderStatus.CONFIRMED
    for ticket in db.scalars(select(Ticket).where(Ticket.order_id == order.id).with_for_update()):
        if ticket.status == TicketStatus.PENDING_PAYMENT:
            ticket.status = TicketStatus.ACTIVE
    db.commit()
    return payment
