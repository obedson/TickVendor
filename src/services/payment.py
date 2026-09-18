"""Payment initialization and idempotent verification service.

Lock order
----------
Every path that concludes a ticket reservation — confirming it, releasing it, or letting it expire
— takes the same three rows in the same order::

    Payment -> Order -> Ticket

`apply_successful_payment` established it, and everything else follows it, because two paths that
take the same rows in opposite orders can deadlock: each ends up holding what the other is waiting
for. So a path that may need more than one of these rows locks its payment first, then the order
that payment belongs to, then that order's tickets — `cancel_pending_checkout` here, and
`expire_pending_orders` and `release_pending_order` in `src.services.ticket`.

Paths that only read are not part of this. `reconcile_payment` takes no row locks at all, and the
refund paths in `src.services.ticket` take none of their own: they act only on an order that has
already settled, so they never contend with the paths that are still deciding whether it will.
"""

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
from src.payments.providers import PaymentProvider, PaymentProviderError
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
        diagnostic = {
            "provider": provider.name,
            "order_id": str(order.id),
            "order_reference": order.reference,
            "error_type": type(exc).__name__,
            "failure_kind": exc.kind if isinstance(exc, PaymentProviderError) else "unexpected",
        }
        if isinstance(exc, PaymentProviderError):
            diagnostic["provider_http_status"] = exc.http_status
            diagnostic["provider_message"] = exc.safe_message
        emit(
            "payment_initialization_failure",
            **diagnostic,
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


# A provider outcome that means "this checkout ended without a payment". These are the same words
# `apply_successful_payment` already fails a payment on, so the two agree on what abandonment is.
ENDED_CHECKOUT_STATUSES = {"failed", "abandoned", "cancelled", "reversed"}

# What may still be released. `pending` is a checkout that has not concluded; `failed` is what
# `verify-reference` records for an abandoned one, and a buyer who then asks for the release is
# asking for exactly the right thing. A settled or refunded payment is never in this set.
RELEASABLE_PAYMENT_STATUSES = {PaymentStatus.PENDING, PaymentStatus.FAILED}


def cancel_pending_checkout(
    db: Session, payment: Payment, provider: PaymentProvider, actor: User
) -> bool:
    """Release the reservation behind a checkout the buyer cancelled.

    Paystack announces only `charge.success`; a buyer who closes its checkout produces no event at
    all, so nothing provider-side reports the abandonment. The buyer's own browser does, and this is
    what it calls. It is the deliberate counterpart to `expire_pending_orders`, which releases the
    same reservation after the timeout when nobody says anything either way.

    Returns whether *this* call released the reservation. A repeat call, or one arriving after the
    payment settled, releases nothing and reports False rather than failing: that outcome has
    already happened, and asking twice must not change it.

    Two races have to survive here:

    * The buyer clicks cancel as the charge settles. The provider is asked first, and a verification
      that reports success refuses the cancellation outright, so a paid reservation is never
      released by a later click. That question is asked outside the lock on purpose — holding a row
      lock across a provider round-trip would block the webhook confirming the same payment.
    * The webhook confirms in between. The payment status is therefore re-read under the row lock,
      and only a payment still in a releasable state proceeds. Confirmation takes the same locks in
      the same order, so whichever arrives second sees the other's committed work.
    """
    if payment.status not in RELEASABLE_PAYMENT_STATUSES:
        return False
    if payment.status == PaymentStatus.PENDING:
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
                detail=(
                    "Payment status could not be confirmed with the provider, so the reservation "
                    "was not released. It is released automatically if the payment never completes."
                ),
            ) from exc
        if verification.successful:
            raise HTTPException(
                status_code=409,
                detail="This payment has completed; your ticket reservation was not released.",
            )
        if verification.status not in ENDED_CHECKOUT_STATUSES:
            raise HTTPException(
                status_code=409,
                detail=(
                    "This payment is still in progress, so the reservation was not released. "
                    "It is released automatically if the payment never completes."
                ),
            )
    locked = db.scalar(
        select(Payment)
        .where(Payment.id == payment.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked is None or locked.status not in RELEASABLE_PAYMENT_STATUSES:
        return False
    order = db.scalar(
        select(Order)
        .where(Order.id == locked.order_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    # Only a reservation still waiting on payment is released. A confirmed order keeps its tickets
    # whatever a stale browser tab believes, and a ticket that has been used or refunded is never
    # among the ones this touches.
    if order is None or order.status != OrderStatus.PENDING:
        return False
    order.status = OrderStatus.CANCELLED
    for ticket in db.scalars(select(Ticket).where(Ticket.order_id == order.id).with_for_update()):
        if ticket.status in {TicketStatus.RESERVED, TicketStatus.PENDING_PAYMENT}:
            ticket.status = TicketStatus.CANCELLED
    locked.status = PaymentStatus.CANCELLED
    locked.failure_reason = "Checkout cancelled by the buyer before payment"
    event = db.get(Event, order.event_id)
    audit(
        db,
        actor_id=actor.id,
        community_id=event.community_id if event else None,
        action="order.cancelled",
        target_type="order",
        target_id=order.id,
        metadata={"reason": "checkout_cancelled_by_buyer", "payment_id": str(locked.id)},
        commit=False,
    )
    db.commit()
    emit("payment_checkout_cancelled", payment_id=str(locked.id), order_id=str(order.id))
    return True


def reconcile_payment(
    db: Session, payment: Payment, provider: PaymentProvider, actor: User
) -> dict[str, object]:
    """Compare local/provider payment data and audit; never silently correct state.

    Deliberately takes no row locks: it reads a payment, its order, and the provider, writes nothing
    but its own audit entry, and so cannot be one half of a lock-order cycle with the paths that do
    conclude reservations. Adding a lock here would buy no safety the audit lacks — the states it
    compares are read once, and a mismatch is reported rather than acted on.
    """
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
