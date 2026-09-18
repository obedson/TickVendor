"""How many tickets one order may hold: one for a free type, the organizer's number for a paid one.

Two rules meet on the same field and pull in opposite directions:

* A free ticket type admits exactly one ticket per order. A price of zero is not a sale, so one buyer
  has nothing legitimate to gain by sweeping the whole allocation in a single checkout.
* A paid ticket type admits exactly what its organizer configured, bounded only by the inventory that
  is left. `max_per_user` is not part of that number — it limits how many tickets one attendee may
  personally redeem, which the server enforces at check-in.

The paid half is written because staging contradicted it: a VIP type configured for ten per order
was offered as one. These tests therefore pin the numbers the purchase surface *reads*, not only the
numbers the purchase path accepts.
"""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import (
    Community,
    Event,
    EventStatus,
    LocationType,
    Membership,
    MembershipRole,
    Organization,
    Profile,
    Ticket,
    TicketStatus,
    TicketType,
    User,
)
from src.security import create_access_token


def build_world(tmp_path, *, name="purchase-quantity.db"):
    engine = create_engine(
        f"sqlite:///{tmp_path / name}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    ids, tokens = {}, {}
    with Session(engine) as db:
        organizer = User(email="qty-organizer@example.com", password_hash="hash")
        buyer = User(email="qty-buyer@example.com", password_hash="hash")
        db.add_all([organizer, buyer])
        db.flush()
        for user, label in ((organizer, "Organizer"), (buyer, "Buyer")):
            db.add(Profile(user_id=user.id, username=f"qty-{user.id.hex[:8]}", display_name=label))
        organization = Organization(owner_id=organizer.id, name="Quantity Org", slug="qty-org")
        db.add(organization)
        db.flush()
        community = Community(
            organization_id=organization.id, name="Quantity Community", slug="qty-community"
        )
        db.add(community)
        db.flush()
        db.add_all([
            Membership(community_id=community.id, user_id=organizer.id, role=MembershipRole.ORGANIZER),
            Membership(community_id=community.id, user_id=buyer.id, role=MembershipRole.MEMBER),
        ])
        starts = datetime.now(UTC) + timedelta(days=3)
        event = Event(
            community_id=community.id, organizer_id=organizer.id, title="Quantity Event",
            slug="qty-event", description="Description", category="technology",
            starts_at=starts, ends_at=starts + timedelta(hours=3),
            location_type=LocationType.ONLINE, status=EventStatus.PUBLISHED,
        )
        db.add(event)
        db.commit()
        ids.update(event=event.id, community=community.id, buyer=buyer.id)
        tokens.update(organizer=create_access_token(organizer.id, "organizer"),
                      buyer=create_access_token(buyer.id, "participant"))

    app = create_app()

    def override_get_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    world = TestClient(app)
    world.ids, world.tokens, world.engine = ids, tokens, engine
    return world


def auth(world, who="buyer"):
    return {"Authorization": f"Bearer {world.tokens[who]}"}


def add_type(world, **body):
    payload = {"name": "Ticket", "price": 0, "currency": "NGN", "quantity": 100,
               "max_per_user": 1, "max_per_order": 4, "visibility": "public"}
    payload.update(body)
    return world.post(
        f"/api/v1/events/{world.ids['event']}/ticket-types",
        json=payload, headers=auth(world, "organizer"),
    )


def edit_type(world, ticket_type_id, body):
    return world.patch(
        f"/api/v1/events/{world.ids['event']}/ticket-types/{ticket_type_id}",
        json=body, headers=auth(world, "organizer"),
    )


def buy(world, ticket_type_id, quantity, key):
    return world.post(
        f"/api/v1/events/{world.ids['event']}/orders",
        json={"ticket_type_id": ticket_type_id, "quantity": quantity, "idempotency_key": key},
        headers=auth(world),
    )


def stored_type(world, ticket_type_id):
    with Session(world.engine) as db:
        return db.get(TicketType, ticket_type_id)


def listing(world):
    response = world.get(
        f"/api/v1/events/{world.ids['event']}/ticket-types", headers=auth(world)
    )
    assert response.status_code == 200, response.text
    return response.json()


# ── A free ticket type admits one ticket per order ───────────────────────────

def test_free_ticket_type_cannot_be_created_above_one_per_order(tmp_path):
    world = build_world(tmp_path)
    free = add_type(world, name="Free", price=0, max_per_order=10)
    assert free.status_code == 201, free.text
    assert free.json()["max_per_order"] == 1
    assert stored_type(world, free.json()["id"]).max_per_order == 1

    # A paid type keeps the organizer's own ceiling: the rule is a property of the price.
    paid = add_type(world, name="Regular", price="5000.00", max_per_order=10)
    assert paid.status_code == 201, paid.text
    assert paid.json()["max_per_order"] == 10
    assert stored_type(world, paid.json()["id"]).max_per_order == 10

    world.engine.dispose()


def test_free_ticket_type_cannot_be_updated_above_one_per_order(tmp_path):
    world = build_world(tmp_path)
    free = add_type(world, name="Free", price=0).json()
    # The shipped form default is 4, so an edit that states it is corrected rather than refused.
    raised = edit_type(world, free["id"], {"max_per_order": 6})
    assert raised.status_code == 200, raised.text
    assert raised.json()["max_per_order"] == 1
    assert stored_type(world, free["id"]).max_per_order == 1

    # A paid type that becomes free in the same payload carries the free ceiling with it.
    paid = add_type(world, name="Regular", price="5000.00", max_per_order=10).json()
    became_free = edit_type(world, paid["id"], {"price": 0})
    assert became_free.status_code == 200, became_free.text
    assert became_free.json()["max_per_order"] == 1
    assert stored_type(world, paid["id"]).max_per_order == 1

    # A paid type is otherwise left exactly as its organizer configured it.
    other = add_type(world, name="VIP", price="1000.00", max_per_order=10).json()
    renamed = edit_type(world, other["id"], {"name": "VIP Plus"})
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["max_per_order"] == 10

    world.engine.dispose()


def test_free_order_quantity_above_one_is_rejected(tmp_path):
    world = build_world(tmp_path)
    free = add_type(world, name="Free", price=0).json()
    over = buy(world, free["id"], 2, "free-quantity-key-0001")
    assert over.status_code == 409, over.text
    assert "at most 1" in over.json()["detail"]

    single = buy(world, free["id"], 1, "free-quantity-key-0002")
    assert single.status_code == 201, single.text
    assert single.json()["status"] == "confirmed"

    # The purchase is the last line of defence: a free ceiling written around the service is still
    # refused, because the model's own default for `max_per_order` is 4.
    with Session(world.engine) as db:
        db.get(TicketType, free["id"]).max_per_order = 4
        db.commit()
    still_refused = buy(world, free["id"], 2, "free-quantity-key-0003")
    assert still_refused.status_code == 409, still_refused.text

    world.engine.dispose()


# ── A paid ticket type sells what its organizer configured ───────────────────

def test_paid_ticket_type_reports_the_configured_per_order_ceiling(tmp_path):
    world = build_world(tmp_path)
    vip = add_type(world, name="VIP", price="1000000.00", quantity=100,
                   max_per_user=1, max_per_order=10).json()
    # The listing is where a buyer's quantity control reads its ceiling from, so the configured
    # number has to survive the round trip instead of collapsing to the per-attendee limit.
    entry = next(item for item in listing(world) if item["id"] == vip["id"])
    assert entry["max_per_order"] == 10
    assert entry["max_per_user"] == 1
    assert entry["availability"] == 100

    world.engine.dispose()


def test_paid_order_accepts_the_configured_quantity(tmp_path):
    world = build_world(tmp_path)
    vip = add_type(world, name="VIP", price="1000.00", quantity=100,
                   max_per_user=1, max_per_order=10).json()
    accepted = buy(world, vip["id"], 3, "paid-quantity-key-0001")
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()["status"] == "pending"
    with Session(world.engine) as db:
        tickets = list(db.scalars(select(Ticket).where(Ticket.order_id == accepted.json()["id"])))
    assert len(tickets) == 3
    assert {ticket.status for ticket in tickets} == {TicketStatus.PENDING_PAYMENT}

    world.engine.dispose()


def test_paid_order_above_the_configured_quantity_is_rejected(tmp_path):
    world = build_world(tmp_path)
    vip = add_type(world, name="VIP", price="1000.00", quantity=100,
                   max_per_user=1, max_per_order=10).json()
    over = buy(world, vip["id"], 11, "paid-quantity-key-0002")
    assert over.status_code == 409, over.text
    assert "at most 10" in over.json()["detail"]

    # The ceiling itself is allowed, so the boundary is the configured number and not one below it.
    allowed = buy(world, vip["id"], 10, "paid-quantity-key-0003")
    assert allowed.status_code == 201, allowed.text

    world.engine.dispose()


def test_max_per_user_does_not_reduce_a_paid_order_quantity(tmp_path):
    world = build_world(tmp_path)
    # `max_per_user` is the per-attendee redemption limit enforced at check-in and its default is
    # one. Reading it as a purchase cap is exactly what clamped every paid type to a single ticket.
    vip = add_type(world, name="VIP", price="1000.00", quantity=100,
                   max_per_user=1, max_per_order=5).json()
    accepted = buy(world, vip["id"], 3, "paid-quantity-key-0004")
    assert accepted.status_code == 201, accepted.text
    with Session(world.engine) as db:
        assert db.query(Ticket).filter_by(order_id=accepted.json()["id"]).count() == 3

    world.engine.dispose()
