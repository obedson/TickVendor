"""Payment initialization, verification, and signed webhook routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.config import settings
from src.database import get_db
from src.models import Order, Payment, User
from src.monitoring import emit
from src.payments.live_providers import FlutterwaveProvider, PaystackProvider, StripeProvider
from src.payments.providers import PaymentProvider, TestPaymentProvider
from src.schemas.payment import (
    PaymentInitializeRequest,
    PaymentInitializeResponse,
    PaymentReferenceVerifyRequest,
    PaymentVerifyRequest,
)
from src.services.payment import apply_successful_payment, initialize_payment, reconcile_payment
from src.services.ticket import refund_order

router = APIRouter(prefix="/payments", tags=["payments"])
_test_provider = TestPaymentProvider()


def get_payment_provider() -> PaymentProvider:
    if settings.payment_provider == "test" or settings.environment in {"development", "test"}:
        return _test_provider
    if settings.payment_provider == "paystack":
        return PaystackProvider(
            settings.paystack_secret_key.get_secret_value() if settings.paystack_secret_key else "",
            settings.paystack_webhook_secret.get_secret_value()
            if settings.paystack_webhook_secret
            else None,
            settings.frontend_url or settings.canonical_url,
        )
    if settings.payment_provider == "flutterwave":
        return FlutterwaveProvider(
            settings.flutterwave_secret_key.get_secret_value()
            if settings.flutterwave_secret_key
            else "",
            settings.flutterwave_webhook_secret.get_secret_value()
            if settings.flutterwave_webhook_secret
            else "",
        )
    if settings.payment_provider == "stripe":
        return StripeProvider(
            settings.stripe_secret_key.get_secret_value() if settings.stripe_secret_key else "",
            settings.stripe_webhook_secret.get_secret_value() if settings.stripe_webhook_secret else None,
        )
    raise HTTPException(status_code=503, detail="Payment provider is not configured")


@router.post("/initialize", response_model=PaymentInitializeResponse)
def initialize(
    payload: PaymentInitializeRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    provider: Annotated[PaymentProvider, Depends(get_payment_provider)],
):
    order = db.get(Order, payload.order_id)
    if order is None or order.user_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    payment, initialized = initialize_payment(db, order, user.email, payload.idempotency_key, provider)
    return PaymentInitializeResponse(
        payment_id=payment.id,
        provider_reference=initialized.provider_reference,
        checkout_url=initialized.checkout_url,
    )


@router.post("/verify-reference")
def verify_reference(
    payload: PaymentReferenceVerifyRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    provider: Annotated[PaymentProvider, Depends(get_payment_provider)],
):
    payment = db.query(Payment).filter_by(
        provider=provider.name,
        provider_reference=payload.provider_reference,
    ).one_or_none()
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    order = db.get(Order, payment.order_id)
    if order is None or order.user_id != user.id:
        raise HTTPException(status_code=404, detail="Payment not found")
    apply_successful_payment(db, payment, provider)
    return {
        "payment_id": str(payment.id),
        "order_id": str(order.id),
        "order_reference": order.reference,
        "status": payment.status.value,
        "order_status": order.status.value,
        "provider_reference": payment.provider_reference,
    }


@router.get("/{payment_id}")
def payment_status(payment_id: UUID, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    order = db.get(Order, payment.order_id)
    if order is None or order.user_id != user.id:
        raise HTTPException(status_code=404, detail="Payment not found")
    return {"payment_id": str(payment.id), "order_id": str(order.id), "order_reference": order.reference,
            "status": payment.status.value, "order_status": order.status.value,
            "provider_reference": payment.provider_reference}


@router.post("/verify")
def verify(
    payload: PaymentVerifyRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    provider: Annotated[PaymentProvider, Depends(get_payment_provider)],
):
    payment = db.get(Payment, payload.payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    order = db.get(Order, payment.order_id)
    if order is None or order.user_id != user.id:
        raise HTTPException(status_code=404, detail="Payment not found")
    apply_successful_payment(db, payment, provider)
    return {"status": payment.status.value}


@router.post("/{payment_id}/refund")
def refund(
    payment_id: UUID, db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    provider: Annotated[PaymentProvider, Depends(get_payment_provider)],
):
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    order = db.get(Order, payment.order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return refund_order(db, order, user, provider)


@router.post("/{payment_id}/reconcile")
def reconcile(
    payment_id: UUID, db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    provider: Annotated[PaymentProvider, Depends(get_payment_provider)],
):
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return reconcile_payment(db, payment, provider, user)


@router.post("/tickets/{ticket_id}/refund")
def refund_ticket(
    ticket_id: UUID, db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    provider: Annotated[PaymentProvider, Depends(get_payment_provider)],
):
    """Refund one ticket of a multi-ticket order; sibling tickets are never affected."""
    from src.models import Ticket
    from src.services.ticket import refund_single_ticket

    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    updated, completed = refund_single_ticket(db, ticket, user, provider)
    return {"ticket_id": str(updated.id), "status": updated.status.value, "completed": completed}


@router.post("/webhooks/{provider_name}")
async def webhook(
    provider_name: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    provider: Annotated[PaymentProvider, Depends(get_payment_provider)],
    x_paystack_signature: Annotated[str | None, Header()] = None,
    x_payment_signature: Annotated[str | None, Header()] = None,
):
    if provider_name != provider.name:
        raise HTTPException(status_code=404, detail="Provider not configured")
    try:
        signature = x_paystack_signature if provider.name == "paystack" else x_payment_signature
        event = provider.verify_webhook(await request.body(), signature)
    except ValueError as exc:
        emit("payment_webhook_failure", provider=provider_name, error_type=type(exc).__name__)
        raise HTTPException(status_code=400, detail="Invalid webhook signature") from exc
    if provider.name == "paystack" and event.get("event") != "charge.success":
        return {"status": "ignored"}
    reference = str(event.get("provider_reference", ""))
    payment = db.query(Payment).filter_by(provider=provider.name, provider_reference=reference).one_or_none()
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    apply_successful_payment(db, payment, provider)
    return {"status": "processed"}
