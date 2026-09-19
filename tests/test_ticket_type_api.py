"""Public ticket inventory response tests.

The listing is the one inventory read that every caller shares, so what it exposes is decided per
caller rather than per route: the public view for anyone who can read the event, and the full
inventory for whoever may configure it. These tests pin both halves of that, and the boundary
between them — community rank and event staff are not the same thing as maintaining the inventory.
"""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import (
    Event,
    EventStaff,
    EventStaffRole,
    Membership,
    MembershipRole,
    PlatformRole,
    TicketType,
    TicketVisibility,
)
from src.security import create_access_token
from tests.test_database import create_event_context, create_user

API = "/api/v1"


def test_event_ticket_types_expose_only_public_inventory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'ticket-types-api.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with Session(engine) as db:
        user, community, event = create_event_context(db)
        db.add(Membership(community_id=community.id, user_id=user.id, role=MembershipRole.MEMBER))
        db.add_all([
            TicketType(event_id=event.id, name="Free", price=0, quantity=10, visibility=TicketVisibility.PUBLIC),
            TicketType(event_id=event.id, name="Invite", price=0, quantity=10, visibility=TicketVisibility.INVITE_ONLY),
        ])
        event.status = "published"
        db.commit(); user_id, event_id = user.id, event.id
    app = create_app()
    def override():
        with sessions() as db: yield db
    app.dependency_overrides[get_db] = override
    response = TestClient(app).get(f"/api/v1/events/{event_id}/ticket-types",
                                   headers={"Authorization": f"Bearer {create_access_token(user_id, 'participant')}"})
    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == ["Free"]
    engine.dispose()


def setup(tmp_path):
    """One community, one published event, and a caller standing in for every listing rule.

    Every caller is a distinct account, so the response can only be explained by the authority they
    hold: the owner and the unrelated Organizer differ by nothing but ``event.organizer_id``, and
    the admin, the member and the staffer differ by nothing but the row that grants them standing.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'ticket-types-api.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with Session(engine) as db:
        owner, community, event = create_event_context(db)
        db.add(Membership(community_id=community.id, user_id=owner.id, role=MembershipRole.ORGANIZER))
        admin = create_user(db, "admin@example.com", "admin")
        organizer = create_user(db, "organizer@example.com", "organizer")
        member = create_user(db, "member@example.com", "member")
        staffer = create_user(db, "staffer@example.com", "staffer")
        super_admin = create_user(db, "super@example.com", "super")
        super_admin.role = PlatformRole.SUPER_ADMIN
        db.add_all([
            Membership(community_id=community.id, user_id=admin.id, role=MembershipRole.ADMIN),
            # An Organizer of the community who does not run this event: rank without ownership.
            Membership(community_id=community.id, user_id=organizer.id, role=MembershipRole.ORGANIZER),
            Membership(community_id=community.id, user_id=member.id, role=MembershipRole.MEMBER),
            Membership(community_id=community.id, user_id=staffer.id, role=MembershipRole.MEMBER),
        ])
        db.add_all([
            TicketType(event_id=event.id, name="Free", price=0, quantity=10, visibility=TicketVisibility.PUBLIC),
            TicketType(event_id=event.id, name="Invite", price=0, quantity=10, visibility=TicketVisibility.INVITE_ONLY),
        ])
        event.status = "published"
        db.commit()
        ids = {
            "community": community.id, "event": event.id, "owner": owner.id, "admin": admin.id,
            "organizer": organizer.id, "member": member.id, "staffer": staffer.id,
            "super_admin": super_admin.id,
        }
    app = create_app()

    def override():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override
    return engine, TestClient(app), ids, sessions


def catalog(client, ids, user_id):
    """The public inventory listing, read as one caller."""
    return client.get(
        f"{API}/events/{ids['event']}/ticket-types",
        headers={"Authorization": f"Bearer {create_access_token(user_id, 'participant')}"},
    )


def names(response):
    assert response.status_code == 200, response.text
    return [item["name"] for item in response.json()]


def set_staff(sessions, event_id, user_id, role, *, is_active=True):
    """Upsert one staff row. ``event_staff`` holds at most one row per (event, user)."""
    with sessions() as db:
        row = db.scalar(select(EventStaff).where(
            EventStaff.event_id == event_id, EventStaff.user_id == user_id
        ))
        if row is None:
            db.add(EventStaff(event_id=event_id, user_id=user_id, role=role, is_active=is_active))
        else:
            row.role, row.is_active = role, is_active
        db.commit()


def set_membership_role(sessions, community_id, user_id, role):
    with sessions() as db:
        row = db.scalar(select(Membership).where(
            Membership.community_id == community_id, Membership.user_id == user_id
        ))
        row.role = role
        db.commit()


def test_a_member_sees_the_ticket_types_on_sale_and_nothing_else(tmp_path):
    """Community membership is not a reason to see what the event is not offering publicly.

    The hidden row is asserted to exist first, so this cannot pass because the fixture failed to
    create it: the filter removes it from the response, the table is not empty.
    """
    engine, client, ids, sessions = setup(tmp_path)
    with sessions() as db:
        stored = sorted(item.name for item in db.scalars(select(TicketType)))
    assert stored == ["Free", "Invite"]
    assert names(catalog(client, ids, ids["member"])) == ["Free"]
    engine.dispose()


def test_an_unrelated_organizer_does_not_see_another_organizers_hidden_inventory(tmp_path):
    """Rank in the community is not authority over an event somebody else runs.

    This is the caller the least-privilege pass was about: the same membership role as the owner,
    past every community-wide gate, and still shown only what is on public sale.
    """
    engine, client, ids, _sessions = setup(tmp_path)
    assert names(catalog(client, ids, ids["organizer"])) == ["Free"]
    engine.dispose()


def test_the_event_owner_sees_the_non_public_inventory_they_configure(tmp_path):
    """The owner is the maintainer here, so the hidden tiers are theirs to see.

    Exactly the ``manage_event`` rule the ticket-type editor already applies — which is also why
    the owner in the legacy expectation at the top of this file, a plain ``MEMBER`` of the
    community, still sees the public view only: owning an event is not by itself the authority to
    configure its inventory.
    """
    engine, client, ids, _sessions = setup(tmp_path)
    assert names(catalog(client, ids, ids["owner"])) == ["Free", "Invite"]
    engine.dispose()


def test_a_community_admin_sees_the_events_non_public_inventory(tmp_path):
    """Community governance reaches the inventory without the admin owning the event."""
    engine, client, ids, _sessions = setup(tmp_path)
    assert names(catalog(client, ids, ids["admin"])) == ["Free", "Invite"]
    engine.dispose()


def test_a_super_admin_sees_the_events_non_public_inventory(tmp_path):
    """Platform authority holds no membership in this community and needs none."""
    engine, client, ids, _sessions = setup(tmp_path)
    assert names(catalog(client, ids, ids["super_admin"])) == ["Free", "Invite"]
    engine.dispose()


def test_event_staff_do_not_gain_the_hidden_inventory(tmp_path):
    """Working the door is not choosing what is on sale.

    Every staff role is operationally attached to this event, and none of them is handed the hidden
    tiers by that attachment: the authority to see them is the authority to configure them, and no
    staff role carries it. The deactivated row is asserted too, so the answer cannot come from the
    assignment merely existing.
    """
    engine, client, ids, sessions = setup(tmp_path)
    for role in EventStaffRole:
        set_staff(sessions, ids["event"], ids["staffer"], role)
        assert names(catalog(client, ids, ids["staffer"])) == ["Free"], role
    set_staff(sessions, ids["event"], ids["staffer"], EventStaffRole.MANAGER, is_active=False)
    assert names(catalog(client, ids, ids["staffer"])) == ["Free"]
    # The same account as the event's owner and an Organizer of its community is a maintainer, so
    # the refusals above are about the staff row and not about the account being turned away.
    with sessions() as db:
        db.get(Event, ids["event"]).organizer_id = ids["staffer"]
        db.commit()
    set_membership_role(sessions, ids["community"], ids["staffer"], MembershipRole.ORGANIZER)
    assert names(catalog(client, ids, ids["staffer"])) == ["Free", "Invite"]
    engine.dispose()
