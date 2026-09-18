"""Focused test: free ticket acquisition flow.

Verifies that a participant can obtain a free (₦0) ticket through the browser
journey without invoking Paystack checkout:
  Event → GET ticket-types → POST orders → ticket status = active → GET tickets/me
"""
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy import event as sa_event
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import (
    Community,
    Event,
    EventCategory,
    EventStatus,
    LocationType,
    Membership,
    MembershipRole,
    MembershipStatus,
    Organization,
    PlatformRole,
    TicketType,
    User,
)
from src.security import create_access_token


def _make_client(tmp_path, db_name="free_ticket.db"):
    engine = create_engine(
        f"sqlite:///{tmp_path / db_name}", connect_args={"check_same_thread": False}
    )

    @sa_event.listens_for(engine, "connect")
    def enable_fk(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()

    def override_get_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), sessions, engine


def test_free_ticket_acquisition_journey(tmp_path):
    """Participant obtains a free ticket; no Paystack checkout is triggered."""
    client, sessions, engine = _make_client(tmp_path)

    with sessions() as db:
        # Seed: organizer, participant, org, community, event, free ticket type.
        organizer = User(
            email="organizer@example.com",
            password_hash="x",
            role=PlatformRole.PARTICIPANT,
        )
        participant = User(
            email="participant@example.com",
            password_hash="x",
            role=PlatformRole.PARTICIPANT,
        )
        db.add_all([organizer, participant])
        db.flush()

        org = Organization(name="Test Org", slug="test-org", owner_id=organizer.id)
        db.add(org)
        db.flush()

        community = Community(
            name="Test Community",
            slug="test-community",
            organization_id=org.id,
        )
        db.add(community)
        db.flush()

        # Organizer membership.
        db.add(Membership(
            community_id=community.id,
            user_id=organizer.id,
            role=MembershipRole.ORGANIZER,
            status=MembershipStatus.ACTIVE,
        ))
        # Participant membership.
        db.add(Membership(
            community_id=community.id,
            user_id=participant.id,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        ))

        # Active event category.
        category = EventCategory(slug="community", name="Community", is_active=True)
        db.add(category)
        db.flush()

        # Published event.
        event = Event(
            community_id=community.id,
            organizer_id=organizer.id,
            title="Free Community Meetup",
            slug="free-community-meetup",
            description="A free community event for testing.",
            category="community",
            location_type=LocationType.ONLINE,
            online_url="https://meet.example.com/test",
            starts_at=datetime.now(UTC) + timedelta(days=1),
            ends_at=datetime.now(UTC) + timedelta(days=1, hours=2),
            status=EventStatus.PUBLISHED,
        )
        db.add(event)
        db.flush()

        # Free ticket type (price = 0).
        ticket_type = TicketType(
            event_id=event.id,
            name="Free Admission",
            price=0,
            currency="NGN",
            quantity=100,
            max_per_user=1,
            visibility="public",
        )
        db.add(ticket_type)
        db.commit()

        event_id = str(event.id)
        ticket_type_id = str(ticket_type.id)
        participant_id = participant.id

    participant_token = create_access_token(participant_id, "participant")
    auth = {"Authorization": f"Bearer {participant_token}"}

    # 1. Discover the event.
    events_response = client.get("/api/v1/events")
    assert events_response.status_code == 200
    event_ids = [e["id"] for e in events_response.json()]
    assert event_id in event_ids

    # 2. List ticket types for the event.
    types_response = client.get(
        f"/api/v1/events/{event_id}/ticket-types", headers=auth
    )
    assert types_response.status_code == 200
    types = types_response.json()
    assert len(types) >= 1
    free_type = next(t for t in types if t["id"] == ticket_type_id)
    assert float(free_type["price"]) == 0.0

    # 3. Create order for the free ticket.
    order_response = client.post(
        f"/api/v1/events/{event_id}/orders",
        json={
            "ticket_type_id": ticket_type_id,
            "quantity": 1,
            "idempotency_key": f"test-free-{participant_id}",
        },
        headers=auth,
    )
    assert order_response.status_code == 201, order_response.text
    order = order_response.json()
    # Free order must be CONFIRMED immediately — no Paystack checkout.
    assert order["status"] == "confirmed", f"Expected confirmed, got {order['status']}"
    # No checkout URL should be present for free orders.
    assert order.get("checkout_url") is None

    # 4. Verify ticket is active in wallet.
    wallet_response = client.get("/api/v1/tickets/me", headers=auth)
    assert wallet_response.status_code == 200
    tickets = wallet_response.json()
    assert len(tickets) >= 1
    ticket = next(t for t in tickets if t["event_id"] == event_id)
    assert ticket["status"] == "active", f"Expected active, got {ticket['status']}"
    assert ticket["qr_token"], "QR token must be present"

    # 5. A buyer may acquire a second free ticket; only redemption is limited to one admission.
    duplicate = client.post(
        f"/api/v1/events/{event_id}/orders",
        json={
            "ticket_type_id": ticket_type_id,
            "quantity": 1,
            "idempotency_key": f"test-free-{participant_id}-2",
        },
        headers=auth,
    )
    assert duplicate.status_code == 201, duplicate.text
    assert duplicate.json()["id"] != order["id"]
    wallet_response = client.get("/api/v1/tickets/me", headers=auth)
    assert wallet_response.status_code == 200
    tickets = wallet_response.json()
    assert len([t for t in tickets if t["event_id"] == event_id]) == 2

    engine.dispose()


def test_free_ticket_does_not_require_payment_initialization(tmp_path):
    """Confirm that a free order never needs payment initialization."""
    client, sessions, engine = _make_client(tmp_path, "free_no_payment.db")

    with sessions() as db:
        organizer = User(email="org2@example.com", password_hash="x", role=PlatformRole.PARTICIPANT)
        participant = User(email="part2@example.com", password_hash="x", role=PlatformRole.PARTICIPANT)
        db.add_all([organizer, participant])
        db.flush()
        org = Organization(name="Org2", slug="org2", owner_id=organizer.id)
        db.add(org)
        db.flush()
        community = Community(name="Comm2", slug="comm2", organization_id=org.id)
        db.add(community)
        db.flush()
        db.add(Membership(community_id=community.id, user_id=organizer.id, role=MembershipRole.ORGANIZER, status=MembershipStatus.ACTIVE))
        db.add(Membership(community_id=community.id, user_id=participant.id, role=MembershipRole.MEMBER, status=MembershipStatus.ACTIVE))
        db.add(EventCategory(slug="community2", name="Community2", is_active=True))
        db.flush()
        event = Event(
            community_id=community.id, organizer_id=organizer.id,
            title="Free Event 2", slug="free-event-2", description="Another free event.",
            category="community2", location_type=LocationType.ONLINE,
            online_url="https://meet.example.com/2",
            starts_at=datetime.now(UTC) + timedelta(days=2),
            ends_at=datetime.now(UTC) + timedelta(days=2, hours=1),
            status=EventStatus.PUBLISHED,
        )
        db.add(event)
        db.flush()
        ticket_type = TicketType(event_id=event.id, name="Free", price=0, currency="NGN", quantity=50, max_per_user=1, visibility="public")
        db.add(ticket_type)
        db.commit()
        event_id, ticket_type_id, participant_id = str(event.id), str(ticket_type.id), participant.id

    auth = {"Authorization": f"Bearer {create_access_token(participant_id, 'participant')}"}
    order = client.post(
        f"/api/v1/events/{event_id}/orders",
        json={"ticket_type_id": ticket_type_id, "quantity": 1, "idempotency_key": "free-no-payment-test-001"},
        headers=auth,
    )
    assert order.status_code == 201
    assert order.json()["status"] == "confirmed"
    # Attempting to initialize payment for a confirmed free order should fail gracefully.
    pay_init = client.post(
        "/api/v1/payments/initialize",
        json={"order_id": order.json()["id"], "idempotency_key": "pay-init-free-test-001"},
        headers=auth,
    )
    # Backend should reject payment initialization for already-confirmed orders.
    assert pay_init.status_code in (400, 409, 422), (
        f"Expected error for free order payment init, got {pay_init.status_code}: {pay_init.text}"
    )
    engine.dispose()
