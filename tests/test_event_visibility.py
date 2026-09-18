"""Public and private event discovery boundaries.

Event discovery is the widest read surface in the product, so every route that can return an
event — the listing, the nearby search, the single-event read and global search — has to agree
on one rule: a published event in a public community is world-readable, and a private
community's events reach only that community's active members. Suspended, unpublished and
deleted events are invisible to everyone.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
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
    TicketType,
    User,
    Venue,
)
from src.security import create_access_token


class World:
    """A seeded installation plus the three callers the visibility matrix needs."""

    def __init__(self, engine, sessions, client, ids, tokens):
        self.engine = engine
        self.sessions = sessions
        self.client = client
        self.ids = ids
        self.tokens = tokens

    def get(self, path, who=None, **params):
        headers = {"Authorization": f"Bearer {self.tokens[who]}"} if who else {}
        return self.client.get(path, params=params, headers=headers)

    def post(self, path, body, who):
        return self.client.post(
            path, json=body, headers={"Authorization": f"Bearer {self.tokens[who]}"}
        )

    def titles(self, path, who=None, **params):
        response = self.get(path, who, **params)
        assert response.status_code == 200, response.text
        return [item["title"] for item in response.json()]


def build_world(tmp_path, *, name="visibility.db"):
    engine = create_engine(
        f"sqlite:///{tmp_path / name}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    ids, tokens = {}, {}
    with Session(engine) as db:
        organizer = User(email="vis-organizer@example.com", password_hash="hash")
        member = User(email="vis-member@example.com", password_hash="hash")
        outsider = User(email="vis-outsider@example.com", password_hash="hash")
        db.add_all([organizer, member, outsider])
        db.flush()
        for user, label in ((organizer, "Organizer"), (member, "Member"), (outsider, "Outsider")):
            db.add(Profile(user_id=user.id, username=f"vis-{user.id.hex[:8]}", display_name=label))
        organization = Organization(owner_id=organizer.id, name="Org", slug="vis-org")
        db.add(organization)
        db.flush()
        open_community = Community(
            organization_id=organization.id, name="Open Community", slug="vis-open", is_public=True
        )
        closed_community = Community(
            organization_id=organization.id, name="Closed Community", slug="vis-closed", is_public=False
        )
        db.add_all([open_community, closed_community])
        db.flush()
        db.add_all([
            Membership(community_id=open_community.id, user_id=organizer.id, role=MembershipRole.ORGANIZER),
            Membership(community_id=closed_community.id, user_id=organizer.id, role=MembershipRole.ORGANIZER),
            # `member` belongs to the private community; `outsider` belongs to neither.
            Membership(community_id=closed_community.id, user_id=member.id, role=MembershipRole.MEMBER),
        ])
        venue = Venue(name="Hall", address="1 Test Road", city="Enugu",
                      latitude=Decimal("6.440000"), longitude=Decimal("7.490000"))
        db.add(venue)
        db.flush()
        starts = datetime.now(UTC) + timedelta(days=2)
        common = {
            "organizer_id": organizer.id, "description": "Description", "category": "technology",
            "starts_at": starts, "ends_at": starts + timedelta(hours=4),
            "location_type": LocationType.PHYSICAL, "venue_id": venue.id,
            "status": EventStatus.PUBLISHED,
        }
        rows = {
            "public": Event(community_id=open_community.id, title="Founders Night",
                            slug="vis-founders-night", **common),
            # Listed after the public event so the soonest-first ordering stays deterministic.
            "private": Event(community_id=closed_community.id, title="Founders Dinner",
                             slug="vis-founders-dinner",
                             **{**common, "starts_at": starts + timedelta(days=1),
                                "ends_at": starts + timedelta(days=1, hours=4)}),
            "draft": Event(community_id=open_community.id, title="Draft Day", slug="vis-draft-day",
                           **{**common, "status": EventStatus.DRAFT}),
            "cancelled": Event(community_id=open_community.id, title="Cancelled Gala",
                               slug="vis-cancelled-gala",
                               **{**common, "status": EventStatus.CANCELLED}),
            "suspended": Event(community_id=open_community.id, title="Suspended Show",
                               slug="vis-suspended-show", **{**common, "is_suspended": True}),
            "deleted": Event(community_id=open_community.id, title="Deleted Meet",
                             slug="vis-deleted-meet", **{**common, "deleted_at": datetime.now(UTC)}),
        }
        db.add_all(list(rows.values()))
        db.flush()
        # One public inventory item per community, so the ticket surface can be checked too.
        public_type = TicketType(event_id=rows["public"].id, name="Open Ticket",
                                 price=0, quantity=50, max_per_order=4)
        private_type = TicketType(event_id=rows["private"].id, name="Closed Ticket",
                                  price=0, quantity=50, max_per_order=4)
        db.add_all([public_type, private_type])
        db.commit()
        ids.update({key: event.id for key, event in rows.items()})
        ids["public_type"] = public_type.id
        ids["private_type"] = private_type.id
        ids["open_community"] = open_community.id
        ids["closed_community"] = closed_community.id
        tokens["organizer"] = create_access_token(organizer.id, "organizer")
        tokens["member"] = create_access_token(member.id, "participant")
        tokens["outsider"] = create_access_token(outsider.id, "participant")

    app = create_app()

    def override_get_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    return World(engine, sessions, TestClient(app), ids, tokens)


def test_guests_and_non_members_see_only_public_community_events(tmp_path):
    world = build_world(tmp_path)
    # The private community's event and every non-published event stay out of the listing,
    # for an anonymous guest and for an authenticated non-member alike.
    for who in (None, "outsider"):
        assert world.titles("/api/v1/events", who) == ["Founders Night"]
    # The organizer runs both communities, so both events are theirs to see.
    assert world.titles("/api/v1/events", "organizer") == ["Founders Night", "Founders Dinner"]

    world.engine.dispose()


def test_private_community_member_sees_its_own_events(tmp_path):
    world = build_world(tmp_path)
    assert world.titles("/api/v1/events", "member") == ["Founders Night", "Founders Dinner"]
    # Non-published events stay hidden even from the community that owns them.
    assert "Draft Day" not in world.titles("/api/v1/events", "organizer")

    world.engine.dispose()


def test_single_event_read_applies_the_same_boundary(tmp_path):
    world = build_world(tmp_path)
    for who in (None, "outsider"):
        assert world.get(f"/api/v1/events/{world.ids['public']}", who).status_code == 200
        # A private event is indistinguishable from a missing one.
        assert world.get(f"/api/v1/events/{world.ids['private']}", who).status_code == 404
    assert world.get(f"/api/v1/events/{world.ids['private']}", "member").status_code == 200
    assert world.get(f"/api/v1/events/{world.ids['draft']}", "organizer").status_code == 404
    assert world.get(f"/api/v1/events/{world.ids['suspended']}", "organizer").status_code == 404

    world.engine.dispose()


def test_nearby_search_applies_the_same_boundary(tmp_path):
    world = build_world(tmp_path)
    params = {"latitude": 6.44, "longitude": 7.49, "radius_km": 25}
    for who in (None, "outsider"):
        assert world.titles("/api/v1/events/nearby", who, **params) == ["Founders Night"]
    assert world.titles("/api/v1/events/nearby", "member", **params) == [
        "Founders Night", "Founders Dinner",
    ]

    world.engine.dispose()


def test_global_search_cannot_reach_a_private_community(tmp_path):
    world = build_world(tmp_path)

    def hits(who):
        response = world.get("/api/v1/search", who, q="founders")
        assert response.status_code == 200, response.text
        return sorted(item["title"] for item in response.json()["events"])

    # Both events share the searchable word "Founders"; only membership separates them.
    assert hits("member") == ["Founders Dinner", "Founders Night"]
    assert hits("outsider") == ["Founders Night"]

    world.engine.dispose()


def test_private_community_inventory_is_neither_readable_nor_purchasable(tmp_path):
    world = build_world(tmp_path)
    closed = f"/api/v1/events/{world.ids['private']}/ticket-types"
    opened = f"/api/v1/events/{world.ids['public']}/ticket-types"
    # Prices are event information: a signed-in non-member learns nothing about the private event.
    assert world.get(closed, "outsider").status_code == 404
    assert world.get(closed, "member").status_code == 200
    # The public community stays purchasable by anyone signed in.
    assert world.get(opened, "outsider").status_code == 200

    body = {"ticket_type_id": str(world.ids["private_type"]), "quantity": 1,
            "idempotency_key": "visibility-order-key-1"}
    assert world.post(f"/api/v1/events/{world.ids['private']}/orders", body, "outsider").status_code == 404
    assert world.post(f"/api/v1/events/{world.ids['private']}/orders", body, "member").status_code == 201

    world.engine.dispose()


def test_invalid_or_revoked_token_degrades_to_the_anonymous_view(tmp_path):
    world = build_world(tmp_path)
    headers = {"Authorization": "Bearer not-a-real-token"}
    response = world.client.get("/api/v1/events", headers=headers)
    assert response.status_code == 200
    assert [item["title"] for item in response.json()] == ["Founders Night"]
    assert world.client.get(
        f"/api/v1/events/{world.ids['private']}", headers=headers
    ).status_code == 404

    world.engine.dispose()


def test_revoking_publication_hides_the_event_again(tmp_path):
    world = build_world(tmp_path)
    with Session(world.engine) as db:
        event = db.get(Event, world.ids["public"])
        event.status = EventStatus.DRAFT
        db.commit()
    assert world.titles("/api/v1/events", "outsider") == []
    assert world.get(f"/api/v1/events/{world.ids['public']}", "outsider").status_code == 404

    world.engine.dispose()


def test_deactivating_a_community_hides_its_events(tmp_path):
    world = build_world(tmp_path)
    with Session(world.engine) as db:
        db.get(Community, world.ids["open_community"]).is_active = False
        db.commit()
    # Membership does not survive a deactivated community: its events vanish for everyone,
    # including the organizer who runs it.
    assert world.titles("/api/v1/events", "outsider") == []
    assert world.titles("/api/v1/events", "organizer") == ["Founders Dinner"]
    assert world.get(f"/api/v1/events/{world.ids['public']}", "organizer").status_code == 404

    world.engine.dispose()
