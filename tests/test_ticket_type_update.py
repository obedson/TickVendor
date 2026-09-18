"""Ticket type maintenance: who may edit, what may change, and what must not.

A ticket type is forward-looking configuration, but it is also the thing issued tickets point
at. These tests pin the boundary: organizers maintain their own inventory, outsiders and
participants cannot touch it, and an edit can never restate what a buyer already paid or
withdraw inventory that tickets already hold.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import src.models  # noqa: F401
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
    Profile,
    Ticket,
    TicketStatus,
    TicketType,
    TicketVisibility,
    User,
)
from src.security import create_access_token


def build_world(tmp_path, *, name="ticket-type-update.db"):
    engine = create_engine(
        f"sqlite:///{tmp_path / name}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    ids, tokens = {}, {}
    with Session(engine) as db:
        organizer = User(email="tt-organizer@example.com", password_hash="hash")
        participant = User(email="tt-participant@example.com", password_hash="hash")
        foreign = User(email="tt-foreign@example.com", password_hash="hash")
        db.add_all([organizer, participant, foreign])
        db.flush()
        for user, label in ((organizer, "Organizer"), (participant, "Participant"), (foreign, "Foreign")):
            db.add(Profile(user_id=user.id, username=f"tt-{user.id.hex[:8]}", display_name=label))
        organization = Organization(owner_id=organizer.id, name="Org", slug="tt-org")
        foreign_organization = Organization(owner_id=foreign.id, name="Other Org", slug="tt-other-org")
        db.add_all([organization, foreign_organization])
        db.flush()
        community = Community(organization_id=organization.id, name="Community", slug="tt-community")
        other_community = Community(
            organization_id=foreign_organization.id, name="Other", slug="tt-other"
        )
        db.add_all([community, other_community])
        db.flush()
        db.add_all([
            Membership(community_id=community.id, user_id=organizer.id, role=MembershipRole.ORGANIZER),
            Membership(community_id=community.id, user_id=participant.id, role=MembershipRole.MEMBER),
            Membership(community_id=other_community.id, user_id=foreign.id, role=MembershipRole.ORGANIZER),
        ])
        starts = datetime.now(UTC) + timedelta(days=2)
        event = Event(
            community_id=community.id, organizer_id=organizer.id, title="Maintenance Event",
            slug="tt-maintenance", description="Description", category="technology",
            starts_at=starts, ends_at=starts + timedelta(hours=4),
            location_type=LocationType.ONLINE, status=EventStatus.PUBLISHED,
        )
        other_event = Event(
            community_id=other_community.id, organizer_id=foreign.id, title="Foreign Event",
            slug="tt-foreign-event", description="Description", category="technology",
            starts_at=starts, ends_at=starts + timedelta(hours=4),
            location_type=LocationType.ONLINE, status=EventStatus.PUBLISHED,
        )
        db.add_all([event, other_event])
        db.flush()
        ticket_type = TicketType(
            event_id=event.id, name="Regular", price=Decimal("5000.00"), currency="NGN",
            quantity=100, max_per_user=2, max_per_order=4,
        )
        foreign_type = TicketType(
            event_id=other_event.id, name="Foreign", price=Decimal("1000.00"), quantity=10,
            max_per_user=1, max_per_order=2,
        )
        db.add_all([ticket_type, foreign_type])
        db.commit()
        ids.update(event=event.id, other_event=other_event.id, ticket_type=ticket_type.id,
                   foreign_type=foreign_type.id, community=community.id,
                   other_community=other_community.id)
        tokens.update(organizer=create_access_token(organizer.id, "organizer"),
                      participant=create_access_token(participant.id, "participant"),
                      foreign=create_access_token(foreign.id, "organizer"))

    app = create_app()

    def override_get_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    world = TestClient(app)
    world.ids, world.tokens, world.engine, world.sessions = ids, tokens, engine, sessions
    return world


def patch(world, body, who="organizer", ticket_type="ticket_type"):
    return world.patch(
        f"/api/v1/events/{world.ids['event']}/ticket-types/{world.ids[ticket_type]}",
        json=body, headers={"Authorization": f"Bearer {world.tokens[who]}"},
    )


def issue_ticket(world):
    """Commit one capacity-holding ticket so the type is no longer purely forward-looking."""
    with Session(world.engine) as db:
        buyer_id = db.scalar(select(User.id).where(User.email == "tt-participant@example.com"))
        order = Order(
            reference="TT-ORDER-1", idempotency_key="tt-order-key-1", user_id=buyer_id,
            event_id=world.ids["event"], total_amount=Decimal("5000.00"),
            status=OrderStatus.CONFIRMED,
        )
        db.add(order)
        db.flush()
        db.add(Ticket(
            public_id="TTTICKET0000000000000001", qr_token="tt-qr-token-1",
            order_id=order.id, event_id=world.ids["event"],
            ticket_type_id=world.ids["ticket_type"], purchaser_id=buyer_id,
            attendee_id=buyer_id, status=TicketStatus.ACTIVE,
        ))
        db.commit()


def test_organizer_can_maintain_forward_looking_fields(tmp_path):
    world = build_world(tmp_path)
    response = patch(world, {"max_per_order": 6, "name": "Regular Plus"})
    assert response.status_code == 200, response.text
    assert response.json()["max_per_order"] == 6
    assert response.json()["name"] == "Regular Plus"
    # The identifier and owning event are not editable through this payload.
    assert response.json()["id"] == str(world.ids["ticket_type"])
    assert response.json()["event_id"] == str(world.ids["event"])

    world.engine.dispose()


def test_participants_and_foreign_organizers_cannot_edit_a_ticket_type(tmp_path):
    world = build_world(tmp_path)
    assert patch(world, {"max_per_order": 6}, who="participant").status_code == 403
    # A foreign organizer cannot reach another tenant's event at all.
    assert patch(world, {"max_per_order": 6}, who="foreign").status_code == 403
    assert patch(world, {"max_per_order": 6}, who="foreign",
                 ticket_type="foreign_type").status_code == 403

    world.engine.dispose()


def test_invalid_maintenance_values_are_rejected(tmp_path):
    world = build_world(tmp_path)
    # Purchasing limits keep their schema bounds on the maintenance path too.
    assert patch(world, {"max_per_order": 0}).status_code == 422
    assert patch(world, {"max_per_user": 0}).status_code == 422
    assert patch(world, {"max_per_order": 10_000}).status_code == 422
    assert patch(world, {"price": "-1.00"}).status_code == 422
    assert patch(world, {"name": ""}).status_code == 422
    # A sales window that closes before it opens is refused by the service, not persisted raw.
    window = {
        "sales_start": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        "sales_end": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
    }
    assert patch(world, window).status_code == 422
    # A window supplied one side at a time is still ordered against the stored side.
    with Session(world.engine) as db:
        db.get(TicketType, world.ids["ticket_type"]).sales_start = (
            datetime.now(UTC) + timedelta(days=5)
        )
        db.commit()
    assert patch(world, {
        "sales_end": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
    }).status_code == 422

    world.engine.dispose()


def test_price_and_currency_are_frozen_once_tickets_exist(tmp_path):
    world = build_world(tmp_path)
    # Before any ticket is issued the price is still free to move.
    assert patch(world, {"price": "6000.00"}).status_code == 200
    issue_ticket(world)
    assert patch(world, {"price": "7000.00"}).status_code == 409
    assert patch(world, {"currency": "USD"}).status_code == 409
    # Inventory that issued tickets already hold cannot be withdrawn…
    assert patch(world, {"quantity": 0}).status_code == 409
    # …but the type stays maintainable in every other respect.
    assert patch(world, {"quantity": 5, "max_per_order": 2}).status_code == 200
    with Session(world.engine) as db:
        stored = db.get(TicketType, world.ids["ticket_type"])
        assert stored.price == Decimal("6000.00")
        assert stored.quantity == 5
        assert stored.max_per_order == 2

    world.engine.dispose()


def test_maintenance_never_rewrites_an_issued_ticket_or_order(tmp_path):
    world = build_world(tmp_path)
    issue_ticket(world)
    assert patch(world, {"name": "Renamed", "max_per_order": 9,
                         "visibility": TicketVisibility.INVITE_ONLY.value}).status_code == 200
    with Session(world.engine) as db:
        order = db.query(Order).one()
        ticket = db.query(Ticket).one()
        # The buyer's receipt and admission are untouched by configuration changes.
        assert order.total_amount == Decimal("5000.00")
        assert ticket.ticket_type_id == world.ids["ticket_type"]
        assert ticket.status == TicketStatus.ACTIVE

    world.engine.dispose()


def test_maintenance_is_audited(tmp_path):
    world = build_world(tmp_path)
    assert patch(world, {"max_per_order": 3}).status_code == 200
    with Session(world.engine) as db:
        entry = db.query(AuditLog).filter_by(action="ticket_type.updated").one()
        assert entry.target_id == world.ids["ticket_type"]
        assert entry.metadata_json["fields"] == ["max_per_order"]

    world.engine.dispose()
