"""Payment service tests for verification and webhook idempotency."""

import hashlib
import hmac
import json
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.api.ticket_catalog import list_event_ticket_types
from src.api.tickets import ticket_wallet
from src.database import Base
from src.models import (
    AuditLog,
    Notification,
    Order,
    OrderStatus,
    Payment,
    PaymentStatus,
    Ticket,
    TicketStatus,
    TicketType,
)
from src.payments.live_providers import PaystackProvider, StripeProvider
from src.payments.providers import (
    PaymentInitialization,
    PaymentProviderError,
    PaymentVerification,
    TestPaymentProvider,
)
from src.services.payment import apply_successful_payment, initialize_payment, reconcile_payment
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
        assert db.query(Ticket).filter_by(order_id=order.id).count() == 1
        assert db.query(AuditLog).filter_by(action="payment.verified").count() == 1
        assert db.query(Notification).filter_by(
            deduplication_key=f"paid-ticket-confirmed:{order.id}"
        ).count() == 1
        assert list_event_ticket_types(event.id, db, user)[0]["availability"] == 0
    engine.dispose()


def test_stripe_webhook_signature_contract_is_verified():
    body = b'{"type":"checkout.session.completed","data":{"object":{"id":"cs_123"}}}'
    timestamp = "1700000000"
    secret = "whsec_test"
    signature = "t=" + timestamp + ",v1=" + hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    event = StripeProvider("sk_test", secret).verify_webhook(body, signature)
    assert event == {"event": "checkout.session.completed", "provider_reference": "cs_123"}


def test_paystack_initialization_and_authoritative_verification(monkeypatch):
    calls = []
    class Response:
        def raise_for_status(self): pass
        def json(self):
            if calls[-1][0] == "post":
                return {"data": {"reference": "ORDER-1", "authorization_url": "https://paystack.test/checkout"}}
            return {"data": {"reference": "ORDER-1", "amount": 12550, "currency": "NGN", "status": "success"}}
    monkeypatch.setattr("src.payments.live_providers.httpx.post", lambda *a, **kw: calls.append(("post", a, kw)) or Response())
    monkeypatch.setattr("src.payments.live_providers.httpx.get", lambda *a, **kw: calls.append(("get", a, kw)) or Response())
    provider = PaystackProvider("sk_test", callback_url="https://staging.example.test")
    initialized = provider.initialize("ORDER-1", Decimal("125.50"), "NGN", "member@example.com")
    verified = provider.verify("ORDER-1")
    assert initialized == PaymentInitialization("ORDER-1", "https://paystack.test/checkout")
    assert verified == PaymentVerification("ORDER-1", Decimal("125.5"), "NGN", "success")
    assert calls[0][2]["json"]["amount"] == 12550
    assert calls[0][1][0] == "https://api.paystack.co/transaction/initialize"
    assert calls[0][2]["headers"]["Authorization"] == "Bearer sk_test"
    assert calls[0][2]["json"]["reference"] == "ORDER-1"
    assert calls[0][2]["json"]["currency"] == "NGN"
    assert calls[0][2]["json"]["email"] == "member@example.com"
    assert calls[0][2]["json"]["callback_url"] == "https://staging.example.test/payment/return"
    assert calls[0][2]["timeout"] == 15


def test_paystack_initialization_classifies_http_timeout_and_invalid_response(monkeypatch):
    provider = PaystackProvider("sk_test", callback_url="https://staging.example.test")
    request = httpx.Request("POST", "https://api.paystack.co/transaction/initialize")

    def rejected(*_args, **_kwargs):
        return httpx.Response(
            401, json={"status": False, "message": "Invalid key"}, request=request
        )

    monkeypatch.setattr("src.payments.live_providers.httpx.post", rejected)
    with pytest.raises(PaymentProviderError) as http_error:
        provider.initialize("ORDER-1", Decimal(100), "NGN", "member@example.com")
    assert http_error.value.kind == "provider_rejection"
    assert http_error.value.http_status == 401
    assert http_error.value.safe_message == "Invalid key"

    def timed_out(*_args, **_kwargs):
        raise httpx.ReadTimeout("timeout", request=request)

    monkeypatch.setattr("src.payments.live_providers.httpx.post", timed_out)
    with pytest.raises(PaymentProviderError) as timeout_error:
        provider.initialize("ORDER-2", Decimal(100), "NGN", "member@example.com")
    assert timeout_error.value.kind == "timeout"

    class InvalidResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"status": True, "data": {}}

    monkeypatch.setattr(
        "src.payments.live_providers.httpx.post", lambda *_args, **_kwargs: InvalidResponse()
    )
    with pytest.raises(PaymentProviderError) as invalid_error:
        provider.initialize("ORDER-3", Decimal(100), "NGN", "member@example.com")
    assert invalid_error.value.kind == "invalid_response"


def test_paystack_webhook_signature_and_event_contract():
    body = json.dumps({"event": "charge.success", "data": {"reference": "ORDER-1"}}).encode()
    secret = "paystack-secret"
    signature = hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()
    provider = PaystackProvider(secret)
    assert provider.verify_webhook(body, signature) == {
        "event": "charge.success", "provider_reference": "ORDER-1",
    }
    with pytest.raises(ValueError):
        provider.verify_webhook(body, "malformed")


class RecordingProvider(TestPaymentProvider):
    name = "paystack"

    def __init__(self):
        self.initializations = 0
        self.verification = PaymentVerification("success-1", Decimal(100), "NGN", "success")

    def initialize(self, reference, amount, currency, email):
        self.initializations += 1
        return PaymentInitialization(reference, f"https://checkout.paystack.test/{reference}")

    def verify(self, provider_reference):
        return self.verification


class FailingInitializationProvider(RecordingProvider):
    def initialize(self, reference, amount, currency, email):
        raise PaymentProviderError(
            "provider_rejection", "Invalid integration configuration", http_status=401
        )


def test_initialization_failure_releases_pending_ticket_reservation(tmp_path, caplog):
    from fastapi import HTTPException

    caplog.set_level("INFO", logger="tickvendor.monitoring")
    engine = create_engine(f"sqlite:///{tmp_path / 'init-failure.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        user, _community, event = create_event_context(db)
        order = Order(
            reference="INIT-FAIL",
            idempotency_key="init-failure-order-key",
            user_id=user.id,
            event_id=event.id,
            total_amount=Decimal(100),
            currency="NGN",
        )
        ticket_type = TicketType(
            event_id=event.id, name="Paid", price=Decimal(100), quantity=1
        )
        db.add_all([order, ticket_type])
        db.flush()
        ticket = Ticket(
            public_id="PUBLICINITFAIL",
            qr_token="f" * 48,
            event_id=event.id,
            ticket_type_id=ticket_type.id,
            attendee_id=user.id,
            order_id=order.id,
            status=TicketStatus.PENDING_PAYMENT,
        )
        db.add(ticket)
        db.commit()

        with pytest.raises(HTTPException) as failed:
            initialize_payment(
                db, order, user.email, "init-failure-payment-key", FailingInitializationProvider()
            )

        assert failed.value.status_code == 502
        assert order.status == OrderStatus.CANCELLED
        assert ticket.status == TicketStatus.CANCELLED
        assert ticket_wallet(db, user) == []
        assert db.query(Payment).count() == 0
        assert db.query(AuditLog).filter_by(action="order.cancelled").count() == 1
        logged = " ".join(record.getMessage() for record in caplog.records)
        assert "provider_rejection" in logged
        assert "provider_http_status" in logged
        assert "INIT-FAIL" in logged
    engine.dispose()


def test_payment_initialization_replay_reuses_checkout_and_conflict_is_rejected(tmp_path):
    from fastapi import HTTPException
    engine = create_engine(f"sqlite:///{tmp_path / 'initialization.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        user, _community, event = create_event_context(db)
        first = Order(reference="INIT-1", idempotency_key="init-order-key-1", user_id=user.id,
                      event_id=event.id, total_amount=Decimal(100), currency="NGN")
        second = Order(reference="INIT-2", idempotency_key="init-order-key-2", user_id=user.id,
                       event_id=event.id, total_amount=Decimal(200), currency="NGN")
        db.add_all([first, second]); db.commit()
        provider = RecordingProvider()
        payment, initialized = initialize_payment(db, first, user.email, "same-payment-key", provider)
        replay, replayed = initialize_payment(db, first, user.email, "same-payment-key", provider)
        assert replay.id == payment.id and replayed == initialized and provider.initializations == 1
        with pytest.raises(HTTPException) as conflict:
            initialize_payment(db, second, user.email, "same-payment-key", provider)
        assert conflict.value.status_code == 409
    engine.dispose()


@pytest.mark.parametrize(
    ("verification", "detail"),
    [
        (PaymentVerification("wrong", Decimal(100), "NGN", "success"), "reference"),
        (PaymentVerification("success-1", Decimal(99), "NGN", "success"), "amount"),
        (PaymentVerification("success-1", Decimal(100), "USD", "success"), "currency"),
        (PaymentVerification("success-1", Decimal(100), "NGN", "failed"), "successful"),
    ],
)
def test_authoritative_payment_verification_rejects_mismatch(tmp_path, verification, detail):
    from fastapi import HTTPException
    engine = create_engine(f"sqlite:///{tmp_path / (detail + '.db')}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        user, _community, event = create_event_context(db)
        order = Order(reference="PAY-V", idempotency_key="verify-order-key", user_id=user.id,
                      event_id=event.id, total_amount=Decimal(100), currency="NGN")
        db.add(order); db.flush()
        payment = Payment(order_id=order.id, provider="paystack", provider_reference="success-1",
                          idempotency_key="verify-payment-key", amount=Decimal(100), currency="NGN")
        db.add(payment); db.commit()
        provider = RecordingProvider(); provider.verification = verification
        with pytest.raises(HTTPException) as rejected:
            apply_successful_payment(db, payment, provider)
        assert detail in rejected.value.detail.lower()
    engine.dispose()


def test_reconciliation_reports_mismatch_without_changing_local_state(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'reconcile.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        user, _community, event = create_event_context(db)
        order = Order(reference="REC-1", idempotency_key="reconcile-order-key", user_id=user.id,
                      event_id=event.id, total_amount=Decimal(100), currency="NGN")
        db.add(order); db.flush()
        payment = Payment(order_id=order.id, provider="paystack", provider_reference="success-1",
                          idempotency_key="reconcile-payment-key", amount=Decimal(100), currency="NGN")
        db.add(payment); db.commit()
        provider = RecordingProvider()
        provider.verification = PaymentVerification("success-1", Decimal(99), "NGN", "success")
        result = reconcile_payment(db, payment, provider, user)
        assert result["mismatches"] == ["amount", "status"]
        assert payment.status == PaymentStatus.PENDING
    engine.dispose()
