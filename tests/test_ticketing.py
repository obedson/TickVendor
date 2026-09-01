"""Ticketing service integration tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import (
    Community,
    Event,
    EventCategory,
    EventStatus,
    Membership,
    MembershipRole,
    Notification,
    Organization,
    Ticket,
    TicketStatus,
    User,
)
from src.schemas.ticket import OrderCreate, TicketTypeCreate
from src.services.ticket import create_order, create_ticket_type, validate_ticket


def setup(db: Session):
    organizer = User(email="ticket-organizer@example.com", password_hash="hash")
    buyer = User(email="buyer@example.com", password_hash="hash")
    outsider = User(email="ticket-outsider@example.com", password_hash="hash")
    db.add_all([organizer, buyer, outsider])
    db.flush()
    org = Organization(owner_id=organizer.id, name="Org", slug="ticket-org")
    db.add(org); db.flush()
    community = Community(organization_id=org.id, name="C", slug="ticket-community")
    db.add(community); db.flush()
    db.add(Membership(community_id=community.id, user_id=organizer.id, role=MembershipRole.ORGANIZER))
    db.add(EventCategory(slug="technology", name="Technology"))
    now = datetime.now(UTC) + timedelta(days=1)
    event_model = Event(
        community_id=community.id, organizer_id=organizer.id, title="Event", slug="ticket-event",
        description="Description", category="technology", starts_at=now,
        ends_at=now + timedelta(hours=2), location_type="online", online_url="https://example.com",
        status=EventStatus.PUBLISHED,
    )
    db.add(event_model); db.commit()
    return organizer, buyer, outsider, event_model


def test_free_order_is_idempotent_wallet_ticket_and_duplicate_scan_is_safe(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'ticket.db'}")
    event.listen(engine, "connect", lambda c, _r: c.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        organizer, buyer, outsider, event_model = setup(db)
        ticket_type = create_ticket_type(db, event_model.id, TicketTypeCreate(
            name="Free", price=Decimal(0), quantity=2, max_per_user=1
        ), organizer)
        payload = OrderCreate(ticket_type_id=ticket_type.id, quantity=1, idempotency_key="safe-order-key-12345")
        order = create_order(db, event_model.id, payload, buyer)
        repeated = create_order(db, event_model.id, payload, buyer)
        assert repeated.id == order.id
        ticket = db.query(Ticket).filter_by(order_id=order.id).one()
        assert ticket.status == TicketStatus.ACTIVE
        assert db.query(Notification).filter_by(notification_type="ticket_confirmed").one().user_id == buyer.id
        with pytest.raises(HTTPException) as limit:
            create_order(db, event_model.id, OrderCreate(
                ticket_type_id=ticket_type.id, quantity=1, idempotency_key="another-safe-key-123"
            ), buyer)
        assert limit.value.status_code == 409
        with pytest.raises(HTTPException):
            validate_ticket(db, event_model.id, ticket.qr_token, outsider)
        result, _ = validate_ticket(db, event_model.id, ticket.qr_token, organizer)
        assert result == "valid"
        result, _ = validate_ticket(db, event_model.id, ticket.qr_token, organizer)
        assert result == "already_used"
    engine.dispose()


def test_non_public_ticket_type_cannot_be_ordered(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'ticket-visibility.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        organizer, buyer, _outsider, event_model = setup(db)
        ticket_type = create_ticket_type(db, event_model.id, TicketTypeCreate(
            name="Invite", price=Decimal(0), quantity=2, visibility="invite_only"), organizer)
        with pytest.raises(HTTPException) as denied:
            create_order(db, event_model.id, OrderCreate(ticket_type_id=ticket_type.id, quantity=1,
                                                         idempotency_key="visibility-key-12345"), buyer)
        assert denied.value.status_code == 403
    engine.dispose()
