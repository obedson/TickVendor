"""Payment status API coverage."""

import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.api.payments import get_payment_provider
from src.database import Base, get_db
from src.main import create_app
from src.models import (
    Membership,
    MembershipRole,
    Order,
    OrderStatus,
    Payment,
    PaymentStatus,
    Profile,
    Ticket,
    TicketStatus,
    TicketType,
    User,
)
from src.payments.providers import TestPaymentProvider
from src.security import create_access_token, hash_password
from tests.test_database import create_event_context


def test_owner_can_read_payment_status_and_other_user_cannot(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'payment-status.db'}", connect_args={"check_same_thread": False}); Base.metadata.create_all(engine); sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        owner, community, event = create_event_context(db); other = User(email="payment-other@example.com", password_hash=hash_password("password-password")); db.add(other); db.flush(); db.add(Profile(user_id=other.id, username="payment-other", display_name="Other")); db.add(Membership(community_id=community.id, user_id=owner.id, role=MembershipRole.MEMBER)); order = Order(reference="STATUS-ORDER", idempotency_key="status-order-key", user_id=owner.id, event_id=event.id, status=OrderStatus.PENDING, total_amount=10, currency="NGN"); db.add(order); db.flush(); db.add(Payment(order_id=order.id, provider="test", provider_reference="status-ref", idempotency_key="status-key", status=PaymentStatus.PENDING, amount=10, currency="NGN")); db.commit(); payment_id = db.query(Payment).one().id; owner_id, other_id = owner.id, other.id
    app = create_app()
    def override():
        with sessions() as db: yield db
    app.dependency_overrides[get_db] = override; client = TestClient(app)
    assert client.get(f"/api/v1/payments/{payment_id}", headers={"Authorization": f"Bearer {create_access_token(owner_id, 'participant')}"}).status_code == 200
    assert client.get(f"/api/v1/payments/{payment_id}", headers={"Authorization": f"Bearer {create_access_token(other_id, 'participant')}"}).status_code == 404
    engine.dispose()


def test_callback_verification_and_webhook_replay_activate_one_ticket(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'payment-callback.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        owner, community, event = create_event_context(db)
        db.add(Membership(
            community_id=community.id,
            user_id=owner.id,
            role=MembershipRole.MEMBER,
        ))
        order = Order(
            reference="success-callback-reference",
            idempotency_key="callback-order-key",
            user_id=owner.id,
            event_id=event.id,
            status=OrderStatus.PENDING,
            total_amount=100,
            currency="NGN",
        )
        ticket_type = TicketType(
            event_id=event.id,
            name="Paid",
            price=100,
            quantity=1,
        )
        db.add_all([order, ticket_type])
        db.flush()
        ticket = Ticket(
            public_id="CALLBACKPUBLIC",
            qr_token="c" * 48,
            event_id=event.id,
            ticket_type_id=ticket_type.id,
            attendee_id=owner.id,
            order_id=order.id,
            status=TicketStatus.PENDING_PAYMENT,
        )
        payment = Payment(
            order_id=order.id,
            provider="test",
            provider_reference=order.reference,
            idempotency_key="callback-payment-key",
            status=PaymentStatus.PENDING,
            amount=100,
            currency="NGN",
        )
        db.add_all([ticket, payment])
        db.commit()
        owner_id = owner.id

    app = create_app()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_payment_provider] = lambda: TestPaymentProvider()
    client = TestClient(app)
    auth = {"Authorization": f"Bearer {create_access_token(owner_id, 'participant')}"}

    callback = client.post(
        "/api/v1/payments/verify-reference",
        json={"provider_reference": "success-callback-reference"},
        headers=auth,
    )
    assert callback.status_code == 200, callback.text
    assert callback.json()["status"] == "successful"

    webhook_body = json.dumps({
        "event": "charge.success",
        "provider_reference": "success-callback-reference",
    }).encode()
    for _ in range(2):
        replay = client.post(
            "/api/v1/payments/webhooks/test",
            content=webhook_body,
            headers={
                "content-type": "application/json",
                "x-payment-signature": "test-signature",
            },
        )
        assert replay.status_code == 200, replay.text

    with sessions() as db:
        assert db.query(Ticket).filter_by(order_id=order.id).count() == 1
        assert db.query(Ticket).filter_by(
            order_id=order.id, status=TicketStatus.ACTIVE
        ).count() == 1
        assert db.query(Payment).filter_by(
            order_id=order.id, status=PaymentStatus.SUCCESSFUL
        ).count() == 1
    engine.dispose()
