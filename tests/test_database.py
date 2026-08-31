"""Focused database behavior tests for constraints and persistence."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import (
    Community,
    Event,
    LocationType,
    Organization,
    Payment,
    PaymentStatus,
    PlatformRole,
    Profile,
    TicketType,
    User,
)


@pytest.fixture
def session(tmp_path):
    database_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{database_path}")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def create_user(session: Session, email: str, username: str) -> User:
    user = User(email=email, password_hash="hashed", role=PlatformRole.PARTICIPANT)
    user.profile = Profile(username=username, display_name=username)
    session.add(user)
    session.flush()
    return user


def create_event_context(session: Session):
    owner = create_user(session, "owner@example.com", "owner")
    organization = Organization(owner_id=owner.id, name="Org", slug="org")
    session.add(organization)
    session.flush()
    community = Community(organization_id=organization.id, name="Community", slug="community")
    session.add(community)
    session.flush()
    now = datetime.now(UTC)
    event_model = Event(
        community_id=community.id,
        organizer_id=owner.id,
        title="Event",
        slug="event",
        description="Description",
        category="community",
        starts_at=now,
        ends_at=now + timedelta(hours=2),
        location_type=LocationType.ONLINE,
    )
    session.add(event_model)
    session.flush()
    return owner, community, event_model


def test_duplicate_user_email_is_rejected(session):
    create_user(session, "member@example.com", "member-one")
    session.commit()
    session.add(User(email="member@example.com", password_hash="other"))

    with pytest.raises(IntegrityError):
        session.commit()


def test_foreign_keys_reject_orphan_community(session):
    session.add(Community(organization_id="00000000-0000-0000-0000-000000000001", name="X", slug="x"))

    with pytest.raises(IntegrityError):
        session.commit()


def test_ticket_inventory_constraints_reject_negative_values(session):
    _owner, _community, event_model = create_event_context(session)
    session.add(
        TicketType(
            event_id=event_model.id,
            name="Invalid",
            price=Decimal("-1.00"),
            quantity=1,
            max_per_user=1,
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_payment_idempotency_key_is_unique(session):
    from src.models import Order

    owner, _community, event_model = create_event_context(session)
    order = Order(
        reference="ORDER-1",
        user_id=owner.id,
        event_id=event_model.id,
        total_amount=Decimal("100.00"),
    )
    session.add(order)
    session.flush()
    session.add_all(
        [
            Payment(
                order_id=order.id,
                provider="test",
                provider_reference="provider-1",
                idempotency_key="same-key",
                status=PaymentStatus.PENDING,
                amount=Decimal("100.00"),
            ),
            Payment(
                order_id=order.id,
                provider="test",
                provider_reference="provider-2",
                idempotency_key="same-key",
                status=PaymentStatus.PENDING,
                amount=Decimal("100.00"),
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        session.commit()
