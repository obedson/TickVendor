"""Releasing a ticket reservation when a buyer walks away from a checkout.

Paystack announces only `charge.success`. A buyer who closes its checkout sends nothing at all, so
until the reservation times out those tickets stay out of the listing even though nobody is buying
them. These tests pin the deliberate release that closes that gap: what it frees, that it frees it
immediately, that asking twice changes nothing, and — the part that matters most — that it can never
release a reservation that was paid for, whatever order the buyer's click and the provider's
confirmation happen to arrive in.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import src.models  # noqa: F401
from src.api.payments import get_payment_provider
from src.database import Base, get_db
from src.main import create_app
from src.models import (
    AuditLog,
    Community,
    Event,
    EventStatus,
    LocationType,
    Membership,
    MembershipRole,
    Order,
    OrderStatus,
    Organization,
    Payment,
    PaymentStatus,
    Profile,
    Ticket,
    TicketStatus,
    User,
)
from src.payments.providers import PaymentVerification, TestPaymentProvider
from src.security import create_access_token


class ScriptedProvider(TestPaymentProvider):
    """A provider whose answer changes, the way a real one's does while a charge settles.

    The provider name stays `test` so the rows, the webhook route, and the dependency all agree on
    one provider, exactly as they do in development.
    """

    name = "test"

    def __init__(self, *statuses):
        self.statuses = list(statuses)
        self.verifications = 0

    def verify(self, provider_reference):
        status = self.statuses[min(self.verifications, len(self.statuses) - 1)]
        self.verifications += 1
        return PaymentVerification(provider_reference, Decimal("100.00"), "NGN", status)


def build_world(tmp_path, *, name="payment-cancellation.db", provider=None):
    engine = create_engine(
        f"sqlite:///{tmp_path / name}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    ids, tokens = {}, {}
    with Session(engine) as db:
        people = {
            "organizer": User(email="cancel-organizer@example.com", password_hash="hash"),
            "buyer": User(email="cancel-buyer@example.com", password_hash="hash"),
            "other": User(email="cancel-other@example.com", password_hash="hash"),
        }
        db.add_all(list(people.values()))
        db.flush()
        for key, user in people.items():
            db.add(Profile(user_id=user.id, username=f"cx-{user.id.hex[:8]}", display_name=key.title()))
        organization = Organization(
            owner_id=people["organizer"].id, name="Cancellation Org", slug="cancel-org"
        )
        db.add(organization)
        db.flush()
        community = Community(
            organization_id=organization.id, name="Cancellation Community", slug="cancel-community"
        )
        db.add(community)
        db.flush()
        for key, user in people.items():
            db.add(Membership(
                community_id=community.id, user_id=user.id,
                role=MembershipRole.ORGANIZER if key == "organizer" else MembershipRole.MEMBER,
            ))
        starts = datetime.now(UTC) + timedelta(days=3)
        event = Event(
            community_id=community.id, organizer_id=people["organizer"].id,
            title="Cancellation Event", slug="cancel-event", description="Description",
            category="technology", starts_at=starts, ends_at=starts + timedelta(hours=3),
            location_type=LocationType.ONLINE, status=EventStatus.PUBLISHED,
        )
        db.add(event)
        db.commit()
        ids.update(event=event.id, community=community.id)
        ids.update({key: user.id for key, user in people.items()})
        tokens.update({
            key: create_access_token(user.id, "organizer" if key == "organizer" else "participant")
            for key, user in people.items()
        })

    app = create_app()

    def override_get_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    if provider is not None:
        app.dependency_overrides[get_payment_provider] = lambda: provider
    world = TestClient(app)
    world.ids, world.tokens, world.engine = ids, tokens, engine
    return world


def auth(world, who="buyer"):
    return {"Authorization": f"Bearer {world.tokens[who]}"}


def add_type(world, **body):
    payload = {"name": "VIP", "price": "100.00", "currency": "NGN", "quantity": 100,
               "max_per_user": 1, "max_per_order": 10, "visibility": "public"}
    payload.update(body)
    response = world.post(
        f"/api/v1/events/{world.ids['event']}/ticket-types",
        json=payload, headers=auth(world, "organizer"),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def buy(world, ticket_type_id, *, quantity=1, key="cancel-order-key-000001", who="buyer"):
    response = world.post(
        f"/api/v1/events/{world.ids['event']}/orders",
        json={"ticket_type_id": ticket_type_id, "quantity": quantity, "idempotency_key": key},
        headers=auth(world, who),
    )
    assert response.status_code == 201, response.text
    return response.json()


def initialize(world, order_id, *, who="buyer", key="cancel-payment-key-000001"):
    response = world.post(
        "/api/v1/payments/initialize",
        json={"order_id": order_id, "idempotency_key": key}, headers=auth(world, who),
    )
    assert response.status_code == 200, response.text
    return response.json()


def release(world, *, who="buyer", **handle):
    return world.post("/api/v1/payments/cancel", json=handle, headers=auth(world, who))


def availability(world, ticket_type_id, *, who="buyer"):
    listing = world.get(
        f"/api/v1/events/{world.ids['event']}/ticket-types", headers=auth(world, who)
    )
    assert listing.status_code == 200, listing.text
    return next(item["availability"] for item in listing.json() if item["id"] == ticket_type_id)


def reservation(world, ticket_type_id, *, who="buyer"):
    """The caller's own pending reservation as the ticket listing reports it."""
    listing = world.get(
        f"/api/v1/events/{world.ids['event']}/ticket-types", headers=auth(world, who)
    )
    assert listing.status_code == 200, listing.text
    return next(
        item["pending_reservation"] for item in listing.json() if item["id"] == ticket_type_id
    )


def rows(world, order_id):
    with Session(world.engine) as db:
        order = db.get(Order, UUID(order_id))
        tickets = list(db.scalars(select(Ticket).where(Ticket.order_id == UUID(order_id))))
        payment = db.scalar(select(Payment).where(Payment.order_id == UUID(order_id)))
        return order, tickets, payment


# ── A checkout in progress holds the tickets it reserved ─────────────────────

def test_a_pending_paid_order_holds_inventory(tmp_path):
    world = build_world(tmp_path)
    ticket_type_id = add_type(world, quantity=2)
    assert availability(world, ticket_type_id) == 2

    order = buy(world, ticket_type_id)
    assert order["status"] == "pending"
    # The reservation is real: nobody else can buy those two tickets while the buyer is paying.
    assert availability(world, ticket_type_id) == 1

    world.engine.dispose()


# ── Cancelling the checkout gives the inventory back straight away ───────────

def test_cancelling_a_checkout_restores_inventory_immediately(tmp_path):
    world = build_world(tmp_path)
    ticket_type_id = add_type(world, quantity=2)
    order = buy(world, ticket_type_id)
    payment = initialize(world, order["id"])
    assert availability(world, ticket_type_id) == 1

    released = release(world, payment_id=payment["payment_id"])
    assert released.status_code == 200, released.text
    body = released.json()
    assert body["released"] is True
    assert body["status"] == "cancelled"
    assert body["order_status"] == "cancelled"
    assert body["event_id"] == str(world.ids["event"])
    # Back on sale now, not when the reservation would have expired.
    assert availability(world, ticket_type_id) == 2

    with Session(world.engine) as db:
        entry = db.query(AuditLog).filter_by(action="order.cancelled").one()
        assert entry.actor_id == world.ids["buyer"]
        assert entry.metadata_json["reason"] == "checkout_cancelled_by_buyer"
        assert entry.metadata_json["payment_id"] == payment["payment_id"]

    world.engine.dispose()


def test_release_accepts_the_provider_reference_the_return_page_holds(tmp_path):
    world = build_world(tmp_path)
    ticket_type_id = add_type(world, quantity=1)
    order = buy(world, ticket_type_id)
    payment = initialize(world, order["id"])

    # This is the browser's real path: the return page holds the reference the provider handed back,
    # and a payment that never succeeded cannot be looked up by its local id from there.
    released = release(world, provider_reference=payment["provider_reference"])
    assert released.status_code == 200, released.text
    assert released.json()["released"] is True
    assert released.json()["payment_id"] == payment["payment_id"]
    assert availability(world, ticket_type_id) == 1

    world.engine.dispose()


def test_cancelled_order_tickets_stop_holding_capacity(tmp_path):
    world = build_world(tmp_path)
    ticket_type_id = add_type(world, quantity=1)
    order = buy(world, ticket_type_id)
    payment = initialize(world, order["id"])
    assert release(world, payment_id=payment["payment_id"]).json()["released"] is True

    holding, tickets, stored = rows(world, order["id"])
    assert holding.status == OrderStatus.CANCELLED
    assert {ticket.status for ticket in tickets} == {TicketStatus.CANCELLED}
    assert stored.status == PaymentStatus.CANCELLED

    # Nothing about this order is outstanding, and the ticket is genuinely back on sale.
    assert availability(world, ticket_type_id) == 1
    taken = buy(world, ticket_type_id, key="cancel-order-key-000002", who="other")
    assert taken["status"] == "pending"

    world.engine.dispose()


def test_repeated_release_is_idempotent(tmp_path):
    world = build_world(tmp_path)
    ticket_type_id = add_type(world, quantity=2)
    order = buy(world, ticket_type_id)
    payment = initialize(world, order["id"])
    assert release(world, payment_id=payment["payment_id"]).json()["released"] is True

    again = release(world, payment_id=payment["payment_id"])
    assert again.status_code == 200, again.text
    assert again.json()["released"] is False
    assert again.json()["status"] == "cancelled"
    assert availability(world, ticket_type_id) == 2

    # The second call changed nothing, including the record of the first.
    with Session(world.engine) as db:
        assert db.query(AuditLog).filter_by(action="order.cancelled").count() == 1

    world.engine.dispose()


def test_only_the_purchaser_can_release_the_reservation(tmp_path):
    world = build_world(tmp_path)
    ticket_type_id = add_type(world, quantity=2)
    order = buy(world, ticket_type_id)
    payment = initialize(world, order["id"])

    refused = release(world, who="other", payment_id=payment["payment_id"])
    assert refused.status_code == 404, refused.text
    # Someone else's checkout is not theirs to give up, and the reservation is untouched.
    assert availability(world, ticket_type_id) == 1

    world.engine.dispose()


# ── A reservation that was paid for is never released ────────────────────────

def test_a_settled_payment_is_never_released(tmp_path):
    world = build_world(tmp_path, name="settled.db", provider=ScriptedProvider("success"))
    # The provider reports this charge as settled, so the order has to match what it reports.
    ticket_type_id = add_type(world, price="100.00", quantity=5, max_per_order=5)
    order = buy(world, ticket_type_id)
    payment = initialize(world, order["id"])
    verified = world.post(
        "/api/v1/payments/verify-reference",
        json={"provider_reference": payment["provider_reference"]}, headers=auth(world),
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["order_status"] == "confirmed"

    released = release(world, payment_id=payment["payment_id"])
    assert released.status_code == 200, released.text
    assert released.json()["released"] is False
    assert released.json()["status"] == "successful"
    assert released.json()["order_status"] == "confirmed"

    settled, tickets, stored = rows(world, order["id"])
    assert settled.status == OrderStatus.CONFIRMED
    assert {ticket.status for ticket in tickets} == {TicketStatus.ACTIVE}
    assert stored.status == PaymentStatus.SUCCESSFUL
    assert availability(world, ticket_type_id) == 4

    world.engine.dispose()


def test_a_charge_that_settles_while_the_buyer_cancels_is_not_released(tmp_path):
    provider = ScriptedProvider("success")
    world = build_world(tmp_path, name="race-provider-wins.db", provider=provider)
    ticket_type_id = add_type(world, price="100.00", quantity=5, max_per_order=5)
    order = buy(world, ticket_type_id)
    payment = initialize(world, order["id"])

    # The buyer clicks cancel at the moment the charge settles. The local row still says pending and
    # only the provider knows better, so the provider is asked before anything is released.
    refused = release(world, payment_id=payment["payment_id"])
    assert refused.status_code == 409, refused.text
    assert "completed" in refused.json()["detail"].lower()

    untouched, tickets, stored = rows(world, order["id"])
    assert stored.status == PaymentStatus.PENDING
    assert untouched.status == OrderStatus.PENDING
    assert {ticket.status for ticket in tickets} == {TicketStatus.PENDING_PAYMENT}
    assert availability(world, ticket_type_id) == 4

    # And the confirmation that was already on its way lands normally.
    landed = world.post(
        "/api/v1/payments/verify-reference",
        json={"provider_reference": payment["provider_reference"]}, headers=auth(world),
    )
    assert landed.status_code == 200, landed.text
    assert landed.json()["order_status"] == "confirmed"

    world.engine.dispose()


def test_a_charge_still_in_flight_is_left_to_its_timeout(tmp_path):
    world = build_world(tmp_path, name="still-running.db", provider=ScriptedProvider("ongoing"))
    ticket_type_id = add_type(world, quantity=2)
    order = buy(world, ticket_type_id)
    payment = initialize(world, order["id"])

    # "We have not heard either way" is not "it failed": a charge that may still succeed is never
    # given up on a buyer's click, and the reservation timeout remains the backstop.
    refused = release(world, payment_id=payment["payment_id"])
    assert refused.status_code == 409, refused.text
    assert "still in progress" in refused.json()["detail"]
    assert availability(world, ticket_type_id) == 1

    untouched, tickets, stored = rows(world, order["id"])
    assert stored.status == PaymentStatus.PENDING
    assert untouched.status == OrderStatus.PENDING
    assert {ticket.status for ticket in tickets} == {TicketStatus.PENDING_PAYMENT}

    world.engine.dispose()


def test_a_confirmation_arriving_after_a_release_does_not_break_state(tmp_path):
    # Abandoned when the buyer gives up on it, then confirmed by the provider a moment later.
    provider = ScriptedProvider("abandoned", "success")
    world = build_world(tmp_path, name="race-webhook-late.db", provider=provider)
    ticket_type_id = add_type(world, price="100.00", quantity=5, max_per_order=5)
    order = buy(world, ticket_type_id)
    payment = initialize(world, order["id"])
    assert release(world, payment_id=payment["payment_id"]).json()["released"] is True

    webhook = world.post(
        "/api/v1/payments/webhooks/test",
        json={"event": "charge.success", "provider_reference": payment["provider_reference"]},
        headers={"x-payment-signature": "test-signature"},
    )
    assert webhook.status_code == 409, webhook.text

    released_order, tickets, stored = rows(world, order["id"])
    # The money is recorded rather than dropped, and flagged for a human…
    assert stored.status == PaymentStatus.SUCCESSFUL
    assert "refund review required" in (stored.failure_reason or "")
    # …while no ticket was activated and no cancelled order quietly became a sale.
    assert released_order.status == OrderStatus.CANCELLED
    assert {ticket.status for ticket in tickets} == {TicketStatus.CANCELLED}
    assert availability(world, ticket_type_id) == 5

    world.engine.dispose()


def test_an_abandoned_reservation_still_expires_on_its_own(tmp_path):
    world = build_world(tmp_path)
    ticket_type_id = add_type(world, quantity=1)
    order = buy(world, ticket_type_id)
    payment = initialize(world, order["id"])

    # Nobody says anything at all: no click, no callback. The reservation simply runs out, which is
    # the fallback the explicit release sits in front of rather than replaces.
    with Session(world.engine) as db:
        stored_order = db.get(Order, UUID(order["id"]))
        stored_order.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()

    # Reading the listing is what sweeps expired reservations.
    assert availability(world, ticket_type_id) == 1
    expired, tickets, stored = rows(world, order["id"])
    assert expired.status == OrderStatus.EXPIRED
    assert {ticket.status for ticket in tickets} == {TicketStatus.EXPIRED}
    assert stored.status == PaymentStatus.CANCELLED
    assert stored.id == UUID(payment["payment_id"])

    # A late release request after the sweep is a no-op, not a second release.
    late = release(world, payment_id=payment["payment_id"])
    assert late.status_code == 200, late.text
    assert late.json()["released"] is False

    world.engine.dispose()


# ── The buyer's own browser is the only thing that reports a closed checkout ─

def test_release_accepts_the_order_id_the_buyers_own_browser_created(tmp_path):
    world = build_world(tmp_path)
    ticket_type_id = add_type(world, quantity=2)
    order = buy(world, ticket_type_id)
    payment = initialize(world, order["id"])
    assert availability(world, ticket_type_id) == 1

    # Closing the provider's checkout sends TickVendor nothing at all: no callback, no reference,
    # no return page. The one handle that survives that is the order the buyer's own browser asked
    # for, so the release has to be reachable by it.
    released = release(world, order_id=order["id"])
    assert released.status_code == 200, released.text
    assert released.json()["released"] is True
    assert released.json()["payment_id"] == payment["payment_id"]
    assert released.json()["order_status"] == "cancelled"
    assert availability(world, ticket_type_id) == 2

    world.engine.dispose()


def test_only_the_purchaser_can_release_by_order_id(tmp_path):
    world = build_world(tmp_path)
    ticket_type_id = add_type(world, quantity=2)
    order = buy(world, ticket_type_id)
    initialize(world, order["id"])

    refused = release(world, who="other", order_id=order["id"])
    assert refused.status_code == 404, refused.text
    assert availability(world, ticket_type_id) == 1

    world.engine.dispose()


def test_a_settled_payment_is_never_released_by_order_id(tmp_path):
    world = build_world(tmp_path, name="settled-by-order.db", provider=ScriptedProvider("success"))
    ticket_type_id = add_type(world, price="100.00", quantity=5, max_per_order=5)
    order = buy(world, ticket_type_id)
    payment = initialize(world, order["id"])
    verified = world.post(
        "/api/v1/payments/verify-reference",
        json={"provider_reference": payment["provider_reference"]}, headers=auth(world),
    )
    assert verified.status_code == 200, verified.text

    # Naming the order instead of the payment changes nothing: what decides is what the provider
    # says about the charge, and it says the money arrived.
    released = release(world, order_id=order["id"])
    assert released.status_code == 200, released.text
    assert released.json()["released"] is False
    assert released.json()["status"] == "successful"
    assert released.json()["order_status"] == "confirmed"
    settled, tickets, stored = rows(world, order["id"])
    assert settled.status == OrderStatus.CONFIRMED
    assert {ticket.status for ticket in tickets} == {TicketStatus.ACTIVE}
    assert stored.status == PaymentStatus.SUCCESSFUL
    assert availability(world, ticket_type_id) == 4

    world.engine.dispose()


def test_the_listing_reports_the_callers_own_pending_reservation(tmp_path):
    world = build_world(tmp_path)
    ticket_type_id = add_type(world, quantity=2)
    order = buy(world, ticket_type_id)
    initialize(world, order["id"])

    # The buyer cannot see why the count dropped, or give the reservation up, unless the listing
    # says it is theirs — and the reservation is what is holding the ticket.
    held = reservation(world, ticket_type_id)
    assert held["order_id"] == order["id"]
    assert held["quantity"] == 1
    assert held["expires_at"] is not None

    assert release(world, order_id=order["id"]).json()["released"] is True
    assert reservation(world, ticket_type_id) is None

    world.engine.dispose()


def test_the_listing_never_reports_another_members_pending_reservation(tmp_path):
    world = build_world(tmp_path)
    ticket_type_id = add_type(world, quantity=2)
    order = buy(world, ticket_type_id)
    initialize(world, order["id"])

    # Inventory is public information; whose checkout is open is not. Someone else's reservation is
    # reported to nobody but them, and a guest is told nothing at all.
    assert reservation(world, ticket_type_id, who="other") is None
    guest = world.get(f"/api/v1/events/{world.ids['event']}/ticket-types")
    assert guest.status_code == 200, guest.text
    assert next(
        item for item in guest.json() if item["id"] == ticket_type_id
    )["pending_reservation"] is None

    world.engine.dispose()


# ── A released reservation is gone, and buying again starts over ─────────────

def test_buying_again_after_a_release_creates_a_fresh_reservation(tmp_path):
    world = build_world(tmp_path)
    ticket_type_id = add_type(world, quantity=2)
    order = buy(world, ticket_type_id, quantity=2)
    initialize(world, order["id"])
    assert availability(world, ticket_type_id) == 0

    assert release(world, order_id=order["id"]).json()["released"] is True
    assert availability(world, ticket_type_id) == 2

    # The released reservation is finished with, so the retry is a new order rather than a replay of
    # the abandoned one, and it holds its own tickets.
    again = buy(world, ticket_type_id, quantity=2, key="cancel-order-key-000002")
    assert again["id"] != order["id"]
    assert again["status"] == "pending"
    assert availability(world, ticket_type_id) == 0
    _, tickets, _ = rows(world, again["id"])
    assert {ticket.status for ticket in tickets} == {TicketStatus.PENDING_PAYMENT}

    world.engine.dispose()


def test_buying_again_while_a_reservation_is_pending_reuses_it(tmp_path):
    world = build_world(tmp_path)
    ticket_type_id = add_type(world, quantity=2)
    order = buy(world, ticket_type_id)
    initialize(world, order["id"])

    # One buyer with one open checkout gets that checkout back. A second order here would be a
    # second hold on the same seat — silently, and without anything to pay for it.
    again = buy(world, ticket_type_id, key="cancel-order-key-000002")
    assert again["id"] == order["id"]
    assert again["reference"] == order["reference"]
    assert availability(world, ticket_type_id) == 1
    _, tickets, _ = rows(world, order["id"])
    assert len(tickets) == 1

    world.engine.dispose()
