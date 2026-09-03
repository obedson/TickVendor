"""Ticket cancellation and refund transition tests."""

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import Order, OrderStatus, Payment, PaymentStatus, Ticket, TicketStatus, TicketType
from src.payments.providers import TestPaymentProvider
from src.services.ticket import cancel_ticket, refund_order
from tests.test_database import create_event_context


def test_ticket_cancel_and_refund_transitions(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'refund.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        user, _community, event = create_event_context(db)
        kind = TicketType(event_id=event.id, name="Paid", price=Decimal(100), quantity=1)
        order = Order(reference="REFUND1", idempotency_key="refund-order-key", user_id=user.id,
                      event_id=event.id, total_amount=Decimal(100), currency="NGN")
        db.add_all([kind, order]); db.flush()
        ticket = Ticket(public_id="REFUNDTICKET", qr_token="r" * 48, event_id=event.id,
                        ticket_type_id=kind.id, attendee_id=user.id, order_id=order.id,
                        status=TicketStatus.ACTIVE)
        payment = Payment(order_id=order.id, provider="test", provider_reference="refund-provider",
                          idempotency_key="refund-payment-key", status=PaymentStatus.SUCCESSFUL,
                          amount=Decimal(100))
        db.add_all([ticket, payment]); db.commit()
        cancel_ticket(db, ticket, user)
        assert ticket.status == TicketStatus.CANCELLED
        refund_order(db, order, user, TestPaymentProvider())
        assert payment.status == PaymentStatus.REFUNDED
        assert ticket.status == TicketStatus.REFUNDED
    engine.dispose()


def test_provider_refund_pending_does_not_claim_local_success(tmp_path):
    class PendingProvider(TestPaymentProvider):
        def refund(self, provider_reference, amount):
            return {"status": "pending", "reference": "refund-1"}

    engine = create_engine(f"sqlite:///{tmp_path / 'refund-pending.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        user, _community, event = create_event_context(db)
        order = Order(reference="REF-1", idempotency_key="refund-order-key", user_id=user.id,
                      event_id=event.id, status=OrderStatus.CONFIRMED, total_amount=100, currency="NGN")
        db.add(order); db.flush()
        payment = Payment(order_id=order.id, provider="paystack", provider_reference="pay-1",
                          idempotency_key="refund-payment-key", amount=100,
                          status=PaymentStatus.SUCCESSFUL)
        db.add(payment); db.commit()
        refund_order(db, order, user, PendingProvider())
        assert payment.status == PaymentStatus.SUCCESSFUL
        assert order.status.value == "confirmed"
        assert payment.provider_metadata["refund_reference"] == "refund-1"
    engine.dispose()
