"""Payment service tests for verification and webhook idempotency."""

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import Order, OrderStatus, Payment, PaymentStatus, Ticket, TicketStatus, TicketType
from src.payments.providers import TestPaymentProvider
from src.services.payment import apply_successful_payment
from tests.test_database import create_event_context


def test_successful_payment_activates_tickets_once(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'payment.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        user, _community, event = create_event_context(db)
        order = Order(reference="PAY-1", idempotency_key="pay-order-key-123", user_id=user.id,
                      event_id=event.id, total_amount=Decimal(100), currency="NGN")
        ticket_type = TicketType(event_id=event.id, name="Paid", price=Decimal(100), quantity=1)
        db.add_all([order, ticket_type]); db.flush()
        ticket = Ticket(public_id="PUBLICPAY1", qr_token="q" * 48, event_id=event.id,
                        ticket_type_id=ticket_type.id, attendee_id=user.id, order_id=order.id,
                        status=TicketStatus.PENDING_PAYMENT)
        db.add(ticket)
        payment = Payment(order_id=order.id, provider="test", provider_reference="success-1",
                          idempotency_key="payment-key-123", amount=Decimal(100))
        db.add(payment); db.flush()
        provider = TestPaymentProvider()
        apply_successful_payment(db, payment, provider)
        apply_successful_payment(db, payment, provider)
        assert payment.status == PaymentStatus.SUCCESSFUL
        assert order.status == OrderStatus.CONFIRMED
        assert ticket.status == TicketStatus.ACTIVE
    engine.dispose()
