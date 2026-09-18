"""Holders, multi-ticket orders, transfers, self check-in/out, and entitlements.

Every rule in this module is enforced by the server: purchase is limited per order, admission
is limited per attendee, transfers are single-use, and redemption credentials are issued only
after eligibility is proven from persisted state and server time.

A free ticket type admits one ticket per order, so the fixtures that acquire several tickets at once
buy a paid type and settle it — a reservation only becomes an admission once the charge is verified.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy import event as sa_event
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import (
    Attendance,
    AttendanceVerification,
    Community,
    EntitlementRedemption,
    Event,
    EventCategory,
    EventStatus,
    ImpactTransaction,
    Membership,
    MembershipRole,
    Notification,
    Order,
    Organization,
    Payment,
    PointRule,
    Profile,
    Ticket,
    TicketAssignmentState,
    TicketStatus,
    TicketTransfer,
    TransferStatus,
    User,
    Venue,
    VerificationMethod,
)
from src.payments.providers import PaymentVerification
from src.schemas.attendance import AttendanceCheckIn
from src.schemas.ticket import (
    EntitlementCreate,
    EntitlementUpdate,
    OrderCreate,
    TicketTypeCreate,
)
from src.services.entitlement import (
    CODE_ALPHABET,
    create_entitlement,
    list_ticket_entitlements,
    redeem_entitlement,
    update_entitlement,
    validate_redemption,
)
from src.services.payment import apply_successful_payment
from src.services.ticket import (
    cancel_single_ticket,
    create_order,
    create_ticket_type,
    validate_ticket,
)
from src.services.ticket_attendance import self_check_in, self_check_out
from src.services.ticket_transfer import (
    TRANSFER_TTL,
    cancel_transfer,
    claim_transfer,
    create_transfer,
    hash_claim_token,
    transfer_preview,
)


def make_db(tmp_path, name="holders.db"):
    engine = create_engine(f"sqlite:///{tmp_path / name}")
    sa_event.listen(engine, "connect", lambda c, _r: c.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    return engine


def setup(db: Session, *, geofence=True, **event_overrides):
    organizer = User(email="holder-organizer@example.com", password_hash="hash")
    buyer = User(email="holder-buyer@example.com", password_hash="hash")
    friend = User(email="holder-friend@example.com", password_hash="hash")
    outsider = User(email="holder-outsider@example.com", password_hash="hash")
    db.add_all([organizer, buyer, friend, outsider])
    db.flush()
    for user, name in ((buyer, "Buyer"), (friend, "Friend"), (outsider, "Outsider")):
        db.add(Profile(user_id=user.id, username=f"user-{user.id.hex[:8]}", display_name=name))
    org = Organization(owner_id=organizer.id, name="Org", slug="holder-org")
    db.add(org)
    db.flush()
    community = Community(organization_id=org.id, name="Holders", slug="holder-community")
    db.add(community)
    db.flush()
    db.add(Membership(community_id=community.id, user_id=organizer.id, role=MembershipRole.ORGANIZER))
    for member in (buyer, friend, outsider):
        db.add(Membership(community_id=community.id, user_id=member.id, role=MembershipRole.MEMBER))
    db.add(EventCategory(slug="technology", name="Technology"))
    venue = None
    if geofence:
        venue = Venue(name="Cafe One", address="1 Test Road", city="Enugu",
                      latitude=Decimal("6.440000"), longitude=Decimal("7.490000"))
        db.add(venue)
        db.flush()
    starts = datetime.now(UTC) + timedelta(days=1)
    values = {
        "community_id": community.id, "organizer_id": organizer.id,
        "title": "Attendance Test Event", "slug": "holder-event",
        "description": "Description", "category": "technology", "starts_at": starts,
        "ends_at": starts + timedelta(hours=8), "location_type": "physical",
        "status": EventStatus.PUBLISHED, "venue_id": venue.id if venue else None,
        "geofence_enabled": geofence, "geofence_radius_meters": 100 if geofence else None,
        "self_check_in_enabled": True, "self_checkout_enabled": True,
    }
    values.update(event_overrides)
    event = Event(**values)
    db.add(event)
    db.commit()
    return organizer, buyer, friend, outsider, community, event


INSIDE = AttendanceCheckIn(latitude=Decimal("6.440100"), longitude=Decimal("7.490100"),
                           accuracy_meters=Decimal(12))
OUTSIDE = AttendanceCheckIn(latitude=Decimal("6.500000"), longitude=Decimal("7.600000"),
                           accuracy_meters=Decimal(12))


class SettlingProvider:
    """A provider that reports the charge it is asked about as settled.

    The fixtures below buy several tickets at once, and a free ticket type admits only one per order,
    so those orders are sales. Their tickets stay reservations until a verified charge activates
    them, which is what this stands in for.
    """

    name = "test"

    def __init__(self, amount: Decimal, currency: str = "NGN"):
        self.amount, self.currency = amount, currency

    def verify(self, provider_reference):
        return PaymentVerification(provider_reference, self.amount, self.currency, "success")


def settle(db: Session, order: Order, *, key="holder-payment-key-000001"):
    """Pay a pending order the way a verified provider charge does."""
    provider = SettlingProvider(order.total_amount, order.currency)
    payment = Payment(
        order_id=order.id, provider=provider.name, provider_reference=order.reference,
        idempotency_key=key, amount=order.total_amount, currency=order.currency,
    )
    db.add(payment)
    db.commit()
    return apply_successful_payment(db, payment, provider)


def issue(db, event, buyer, price=Decimal(0), quantity=1, max_per_user=1, max_per_order=4,
          key="order-key-0000001"):
    ticket_type = create_ticket_type(db, event.id, TicketTypeCreate(
        name="Community Ticket", price=price, quantity=quantity, max_per_user=max_per_user,
        max_per_order=max_per_order,
    ), db.query(User).filter_by(email="holder-organizer@example.com").one())
    order = create_order(db, event.id, OrderCreate(
        ticket_type_id=ticket_type.id, quantity=1, idempotency_key=key,
    ), buyer)
    ticket = db.query(Ticket).filter_by(order_id=order.id).order_by(Ticket.created_at).first()
    return ticket_type, order, ticket


# ── Multi-ticket purchase and holders ────────────────────────────────────────

def test_buyer_may_acquire_multiple_tickets_but_only_one_is_their_admission(tmp_path):
    engine = make_db(tmp_path, "multi.db")
    with Session(engine, expire_on_commit=False) as db:
        organizer, buyer, _friend, _outsider, _community, event = setup(db, geofence=False)
        # Five tickets in one order is a sale, and the tickets only become admissions once the
        # charge behind them is verified.
        ticket_type = create_ticket_type(db, event.id, TicketTypeCreate(
            name="Regular", price=Decimal("1000.00"), quantity=10, max_per_user=1, max_per_order=10,
        ), organizer)
        order = create_order(db, event.id, OrderCreate(
            ticket_type_id=ticket_type.id, quantity=5, idempotency_key="multi-order-key-1",
        ), buyer)
        settle(db, order, key="multi-payment-key-000001")
        tickets = db.query(Ticket).filter_by(order_id=order.id).order_by(Ticket.created_at).all()
        assert len(tickets) == 5
        assert len({ticket.public_id for ticket in tickets}) == 5
        assert len({ticket.qr_token for ticket in tickets}) == 5
        states = [ticket.assignment_state for ticket in tickets]
        assert states.count(TicketAssignmentState.CLAIMED) == 1
        assert states.count(TicketAssignmentState.UNASSIGNED) == 4
        assert all(ticket.purchaser_id == buyer.id for ticket in tickets)
        # The buyer cannot redeem an unassigned ticket for themselves.
        unassigned = next(t for t in tickets if t.assignment_state == TicketAssignmentState.UNASSIGNED)
        assert validate_ticket(db, event.id, unassigned.qr_token, organizer)[0] == "unassigned"
        # The buyer's own ticket is admitted once, and the second attempt is refused.
        claimed = next(t for t in tickets if t.assignment_state == TicketAssignmentState.CLAIMED)
        assert validate_ticket(db, event.id, claimed.qr_token, organizer)[0] == "valid"
        assert validate_ticket(db, event.id, claimed.qr_token, organizer)[0] == "already_used"

    engine.dispose()


def test_per_order_limit_is_organizer_configured(tmp_path):
    engine = make_db(tmp_path, "per-order.db")
    with Session(engine, expire_on_commit=False) as db:
        organizer, buyer, _friend, _outsider, _community, event = setup(db, geofence=False)
        # Paid, because a free type's ceiling is one whatever an organizer configures: this is the
        # number an organizer sets, honoured exactly.
        ticket_type = create_ticket_type(db, event.id, TicketTypeCreate(
            name="Regular", price=Decimal("1000.00"), quantity=50, max_per_user=1, max_per_order=3,
        ), organizer)
        with pytest.raises(HTTPException) as exc:
            create_order(db, event.id, OrderCreate(
                ticket_type_id=ticket_type.id, quantity=4, idempotency_key="per-order-key-0000001",
            ), buyer)
        assert exc.value.status_code == 409
        # Inventory still guards the upper bound.
        order = create_order(db, event.id, OrderCreate(
            ticket_type_id=ticket_type.id, quantity=3, idempotency_key="per-order-key-0000002",
        ), buyer)
        assert db.query(Ticket).filter_by(order_id=order.id).count() == 3

    engine.dispose()


def test_inventory_decrements_across_orders(tmp_path):
    engine = make_db(tmp_path, "inventory.db")
    with Session(engine, expire_on_commit=False) as db:
        organizer, buyer, friend, outsider, _community, event = setup(db, geofence=False)
        # A paid type, because only a sale can put more than one ticket in a single order.
        ticket_type = create_ticket_type(db, event.id, TicketTypeCreate(
            name="Regular", price=Decimal("1000.00"), quantity=3, max_per_user=1, max_per_order=3,
        ), organizer)
        create_order(db, event.id, OrderCreate(
            ticket_type_id=ticket_type.id, quantity=2, idempotency_key="inv-key-1111111111",
        ), buyer)
        create_order(db, event.id, OrderCreate(
            ticket_type_id=ticket_type.id, quantity=1, idempotency_key="inv-key-2222222222",
        ), friend)
        # A fresh buyer takes the last ticket from an empty shelf. The first buyer asking again
        # would be handed their own pending reservation instead — a different rule, tested where
        # reservations are.
        with pytest.raises(HTTPException) as exc:
            create_order(db, event.id, OrderCreate(
                ticket_type_id=ticket_type.id, quantity=1, idempotency_key="inv-key-3333333333",
            ), outsider)
        assert exc.value.status_code == 409

    engine.dispose()


# ── Transfer and claim ───────────────────────────────────────────────────────

def test_transfer_claim_is_single_use_and_moves_the_holder(tmp_path):
    engine = make_db(tmp_path, "transfer.db")
    with Session(engine, expire_on_commit=False) as db:
        _organizer, buyer, friend, outsider, _community, event = setup(db, geofence=False)
        _type, order, ticket = issue(db, event, buyer, key="transfer-order-key-1")
        transfer, token = create_transfer(db, ticket, buyer, recipient_email="friend@example.com")
        assert transfer.status.value == "pending"
        assert transfer.claim_token_hash == hash_claim_token(token)
        assert token not in transfer.claim_token_hash
        assert db.get(Ticket, ticket.id).assignment_state == TicketAssignmentState.INVITATION_SENT

        preview = transfer_preview(db, token)
        assert preview["claimable"] is True
        assert preview["event_title"] == event.title
        assert preview["ticket_type_name"] == "Community Ticket"
        assert "buyer" not in str(preview).lower()

        claimed = claim_transfer(db, token, friend)
        assert claimed.attendee_id == friend.id
        assert claimed.assignment_state == TicketAssignmentState.CLAIMED
        assert claimed.purchaser_id == buyer.id
        order = db.get(Order, claimed.order_id)
        assert order.user_id == buyer.id

        # Single use: the same link cannot be claimed twice, by anyone.
        with pytest.raises(HTTPException) as exc:
            claim_transfer(db, token, outsider)
        assert exc.value.status_code == 409
        assert transfer_preview(db, token)["claimable"] is False

    engine.dispose()


def test_transfer_blocked_after_check_in_and_for_cancelled_tickets(tmp_path):
    engine = make_db(tmp_path, "transfer-blocked.db")
    with Session(engine, expire_on_commit=False) as db:
        _organizer, buyer, _friend, _outsider, _community, event = setup(db, geofence=False)
        _type, _order, ticket = issue(db, event, buyer, key="blocked-order-key-1")
        self_check_in(db, event.id, ticket.id, buyer, None)
        with pytest.raises(HTTPException) as exc:
            create_transfer(db, db.get(Ticket, ticket.id), buyer)
        assert exc.value.status_code == 409

    engine.dispose()


def test_transfer_can_be_cancelled_by_the_holder(tmp_path):
    engine = make_db(tmp_path, "transfer-cancel.db")
    with Session(engine, expire_on_commit=False) as db:
        _organizer, buyer, _friend, _outsider, _community, event = setup(db, geofence=False)
        _type, _order, ticket = issue(db, event, buyer, key="cancel-order-key-1")
        _transfer, token = create_transfer(db, ticket, buyer)
        cancel_transfer(db, db.get(Ticket, ticket.id), buyer)
        assert db.get(Ticket, ticket.id).assignment_state == TicketAssignmentState.CLAIMED
        assert transfer_preview(db, token)["claimable"] is False

    engine.dispose()


def test_expired_transfer_cannot_be_claimed(tmp_path):
    engine = make_db(tmp_path, "transfer-expiry.db")
    with Session(engine, expire_on_commit=False) as db:
        _organizer, buyer, friend, _outsider, _community, event = setup(db, geofence=False)
        _type, _order, ticket = issue(db, event, buyer, key="expiry-order-key-1")
        transfer, token = create_transfer(db, ticket, buyer)
        transfer.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        assert TRANSFER_TTL > timedelta(0)
        db.commit()
        with pytest.raises(HTTPException) as exc:
            claim_transfer(db, token, friend)
        assert exc.value.status_code == 409
        assert db.get(Ticket, ticket.id).attendee_id == buyer.id

    engine.dispose()


# ── Self check-in / checkout ─────────────────────────────────────────────────

def test_self_check_in_enforces_geofence_and_is_idempotent(tmp_path):
    engine = make_db(tmp_path, "self-checkin.db")
    with Session(engine, expire_on_commit=False) as db:
        _organizer, buyer, _friend, _outsider, _community, event = setup(db)
        _type, _order, ticket = issue(db, event, buyer, key="checkin-order-key-1")
        with pytest.raises(HTTPException) as missing:
            self_check_in(db, event.id, ticket.id, buyer, None)
        assert missing.value.status_code == 422
        with pytest.raises(HTTPException) as outside:
            self_check_in(db, event.id, ticket.id, buyer, OUTSIDE)
        assert outside.value.status_code == 422
        assert db.query(Attendance).count() == 0
        state = self_check_in(db, event.id, ticket.id, buyer, INSIDE)
        assert state["checked_in_at"] is not None
        assert "gps" in state["viable_methods"]
        assert db.get(Ticket, ticket.id).status == TicketStatus.USED
        # Repeated check-in is idempotent: one attendance row, one GPS signal, one audit trail.
        again = self_check_in(db, event.id, ticket.id, buyer, INSIDE)
        assert again["attendance_id"] == state["attendance_id"]
        assert db.query(Attendance).count() == 1
        verifications = db.query(AttendanceVerification).filter_by(
            attendance_id=state["attendance_id"], method=VerificationMethod.GPS
        ).count()
        assert verifications == 1

    engine.dispose()


def test_self_check_in_refuses_when_disabled_or_unclaimed(tmp_path):
    engine = make_db(tmp_path, "self-checkin-guard.db")
    with Session(engine, expire_on_commit=False) as db:
        _organizer, buyer, _friend, _outsider, _community, event = setup(
            db, geofence=False, self_check_in_enabled=False
        )
        _type, _order, ticket = issue(db, event, buyer, key="guard-order-key-1")
        with pytest.raises(HTTPException) as exc:
            self_check_in(db, event.id, ticket.id, buyer, None)
        assert exc.value.status_code == 409

    engine.dispose()


def test_self_check_out_requires_check_in_and_computes_duration(tmp_path):
    engine = make_db(tmp_path, "self-checkout.db")
    with Session(engine, expire_on_commit=False) as db:
        _organizer, buyer, _friend, _outsider, _community, event = setup(db)
        _type, _order, ticket = issue(db, event, buyer, key="checkout-order-key-1")
        with pytest.raises(HTTPException) as early:
            self_check_out(db, event.id, ticket.id, buyer, None)
        assert early.value.status_code == 409
        self_check_in(db, event.id, ticket.id, buyer, INSIDE)
        attendance = db.query(Attendance).one()
        attendance.checked_in_at = datetime.now(UTC) - timedelta(hours=2)
        db.commit()
        state = self_check_out(db, event.id, ticket.id, buyer, INSIDE)
        assert state["checked_out_at"] is not None
        assert 7100 <= state["duration_seconds"] <= 7300
        again = self_check_out(db, event.id, ticket.id, buyer, INSIDE)
        assert again["checked_out_at"] == state["checked_out_at"]
        assert again["duration_seconds"] == state["duration_seconds"]

    engine.dispose()


def test_checkout_earliest_time_and_geofence_are_enforced(tmp_path):
    engine = make_db(tmp_path, "checkout-guard.db")
    with Session(engine, expire_on_commit=False) as db:
        _organizer, buyer, _friend, _outsider, _community, event = setup(db, geofence=False)
        event.checkout_opens_at = datetime.now(UTC) + timedelta(hours=1)
        db.commit()
        _type, _order, ticket = issue(db, event, buyer, key="checkout-guard-key-1")
        self_check_in(db, event.id, ticket.id, buyer, None)
        with pytest.raises(HTTPException) as early:
            self_check_out(db, event.id, ticket.id, buyer, None)
        assert early.value.status_code == 409

    engine.dispose()


def test_cancelled_ticket_cannot_check_out(tmp_path):
    engine = make_db(tmp_path, "checkout-cancelled.db")
    with Session(engine, expire_on_commit=False) as db:
        _organizer, buyer, _friend, _outsider, _community, event = setup(db, geofence=False)
        _type, _order, ticket = issue(db, event, buyer, key="cancel-checkout-key-1")
        cancel_single_ticket(db, db.get(Ticket, ticket.id), buyer)
        with pytest.raises(HTTPException) as exc:
            self_check_out(db, event.id, ticket.id, buyer, None)
        assert exc.value.status_code == 409

    engine.dispose()


# ── Entitlements and redemption ──────────────────────────────────────────────

def meal(db, event, organizer, ticket_type, **overrides):
    values = {
        "ticket_type_id": ticket_type.id, "name": "Lunch", "requires_check_in": True,
        "requires_geofence": True, "requires_staff_validation": True, "one_time": True,
        "redemption_mode": "either",
    }
    values.update(overrides)
    return create_entitlement(db, event, EntitlementCreate(**values), organizer)


def test_entitlement_is_locked_until_every_condition_is_met(tmp_path):
    engine = make_db(tmp_path, "entitlement-lock.db")
    with Session(engine, expire_on_commit=False) as db:
        organizer, buyer, _friend, _outsider, _community, event = setup(db)
        ticket_type, _order, ticket = issue(db, event, buyer, key="entitlement-key-1")
        meal(db, event, organizer, ticket_type)

        locked = list_ticket_entitlements(db, ticket)[0]
        assert locked["status"] == "locked" and locked["locked_reason"] == "Check in first"

        self_check_in(db, event.id, ticket.id, buyer, INSIDE)
        available = list_ticket_entitlements(db, ticket, point=INSIDE)[0]
        assert available["status"] == "available" and available["locked_reason"] is None

        # Geofence is re-checked on demand: outside the venue the perk is locked again.
        outside = list_ticket_entitlements(db, ticket, point=OUTSIDE)[0]
        assert outside["status"] == "locked" and outside["locked_reason"] == "Must be inside venue"

    engine.dispose()


def test_meal_time_window_uses_server_time(tmp_path):
    engine = make_db(tmp_path, "entitlement-window.db")
    with Session(engine, expire_on_commit=False) as db:
        organizer, buyer, _friend, _outsider, _community, event = setup(db, geofence=False)
        ticket_type, _order, ticket = issue(db, event, buyer, key="window-key-0000001")
        entitlement = meal(
            db, event, organizer, ticket_type, requires_geofence=False,
            redemption_starts_at=datetime.now(UTC) + timedelta(hours=3),
        )
        self_check_in(db, event.id, ticket.id, buyer, None)
        pending = list_ticket_entitlements(db, ticket)[0]
        assert pending["status"] == "locked" and pending["locked_reason"].startswith("Available from")
        update_entitlement(db, event, db.get(type(entitlement), entitlement.id),
                           EntitlementUpdate(redemption_starts_at=datetime.now(UTC) - timedelta(minutes=1)), organizer)
        assert list_ticket_entitlements(db, ticket)[0]["status"] == "available"

    engine.dispose()


def test_checkout_and_minimum_duration_gate_an_entitlement(tmp_path):
    engine = make_db(tmp_path, "entitlement-checkout.db")
    with Session(engine, expire_on_commit=False) as db:
        organizer, buyer, _friend, _outsider, _community, event = setup(db, geofence=False)
        ticket_type, _order, ticket = issue(db, event, buyer, key="gift-key-00000001")
        meal(db, event, organizer, ticket_type, name="Gift Pack", requires_geofence=False,
             requires_checkout=True, min_attendance_minutes=240)
        self_check_in(db, event.id, ticket.id, buyer, None)
        assert list_ticket_entitlements(db, ticket)[0]["locked_reason"] == "Available after checkout"
        attendance = db.query(Attendance).one()
        attendance.checked_in_at = datetime.now(UTC) - timedelta(hours=1)
        attendance.checked_out_at = datetime.now(UTC)
        attendance.duration_seconds = 3600
        db.commit()
        assert list_ticket_entitlements(db, ticket)[0]["locked_reason"] == "Minimum attendance not yet reached"
        attendance.duration_seconds = 5 * 3600
        db.commit()
        assert list_ticket_entitlements(db, ticket)[0]["status"] == "available"

    engine.dispose()


def test_redemption_credential_is_short_lived_single_use_and_hashed(tmp_path):
    engine = make_db(tmp_path, "redeem.db")
    with Session(engine, expire_on_commit=False) as db:
        organizer, buyer, _friend, outsider, _community, event = setup(db)
        ticket_type, _order, ticket = issue(db, event, buyer, key="redeem-key-000001")
        entitlement = meal(db, event, organizer, ticket_type)
        with pytest.raises(HTTPException) as before:
            redeem_entitlement(db, event.id, ticket, entitlement.id, buyer, point=INSIDE)
        assert before.value.status_code == 409
        self_check_in(db, event.id, ticket.id, buyer, INSIDE)
        issued = redeem_entitlement(db, event.id, ticket, entitlement.id, buyer, point=INSIDE)
        assert issued["status"] == "issued"
        code = issued["code"]
        assert len(code) == 4 and set(code) <= set(CODE_ALPHABET)
        record = db.query(EntitlementRedemption).one()
        assert code not in (record.code_hash, record.qr_token_hash)
        assert issued["qr_payload"] not in (record.code_hash, record.qr_token_hash)
        assert list_ticket_entitlements(db, ticket, point=INSIDE)[0]["status"] == "available"

        # An unauthorized member cannot redeem somebody else's benefit.
        with pytest.raises(HTTPException) as denied:
            validate_redemption(db, event.id, outsider, code=code)
        assert denied.value.status_code == 403
        # The wrong event never matches the credential.
        other = Event(community_id=event.community_id, organizer_id=event.organizer_id,
                      title="Other", slug="other-event", description="d", category="technology",
                      starts_at=event.starts_at, ends_at=event.ends_at, location_type="online",
                      status=EventStatus.PUBLISHED)
        db.add(other)
        db.commit()
        with pytest.raises(HTTPException) as wrong_event:
            validate_redemption(db, other.id, organizer, code=code)
        assert wrong_event.value.status_code == 404

        # The entitlement requires venue presence, so staff validation without a location is refused.
        with pytest.raises(HTTPException) as no_location:
            validate_redemption(db, event.id, organizer, code=code)
        assert no_location.value.status_code == 409
        result = validate_redemption(db, event.id, organizer, code=code, point=INSIDE)
        assert result["result"] == "redeemed"
        assert result["entitlement"] == "Lunch"
        assert result["attendee"].startswith("Buyer")
        assert result["remaining"] == 0
        # Atomic single use: a second scan of the same credential is refused.
        with pytest.raises(HTTPException) as repeat:
            validate_redemption(db, event.id, organizer, code=code, point=INSIDE)
        assert repeat.value.status_code == 409
        assert list_ticket_entitlements(db, ticket, point=INSIDE)[0]["status"] == "redeemed"

    engine.dispose()


def test_redemption_credentials_are_random_and_expire(tmp_path):
    engine = make_db(tmp_path, "redeem-expiry.db")
    with Session(engine, expire_on_commit=False) as db:
        organizer, buyer, friend, _outsider, _community, event = setup(db)
        ticket_type, _order, ticket = issue(db, event, buyer, key="random-key-000001")
        entitlement = meal(db, event, organizer, ticket_type)
        self_check_in(db, event.id, ticket.id, buyer, INSIDE)
        first = redeem_entitlement(db, event.id, ticket, entitlement.id, buyer, point=INSIDE)
        # Re-issuing replaces the previous credential, so only one is ever live.
        second = redeem_entitlement(db, event.id, ticket, entitlement.id, buyer, point=INSIDE)
        assert second["code"] != first["code"]
        with pytest.raises(HTTPException) as replaced:
            validate_redemption(db, event.id, organizer, code=first["code"])
        assert replaced.value.status_code == 409
        record = db.query(EntitlementRedemption).filter_by(status="issued").one()
        record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
        with pytest.raises(HTTPException) as expired:
            validate_redemption(db, event.id, organizer, code=second["code"])
        assert expired.value.status_code == 409
        assert friend.id != buyer.id

    engine.dispose()


def test_self_service_entitlement_redeems_without_a_credential(tmp_path):
    engine = make_db(tmp_path, "self-service.db")
    with Session(engine, expire_on_commit=False) as db:
        organizer, buyer, _friend, _outsider, _community, event = setup(db, geofence=False)
        ticket_type, _order, ticket = issue(db, event, buyer, key="self-service-key-1")
        entitlement = meal(db, event, organizer, ticket_type, name="Drink",
                           requires_geofence=False, requires_staff_validation=False)
        self_check_in(db, event.id, ticket.id, buyer, None)
        result = redeem_entitlement(db, event.id, ticket, entitlement.id, buyer)
        assert result["status"] == "redeemed"
        assert db.query(EntitlementRedemption).count() == 0
        assert list_ticket_entitlements(db, ticket)[0]["status"] == "redeemed"

    engine.dispose()


def test_deactivating_an_entitlement_revokes_outstanding_perks(tmp_path):
    engine = make_db(tmp_path, "revoke.db")
    with Session(engine, expire_on_commit=False) as db:
        organizer, buyer, _friend, _outsider, _community, event = setup(db, geofence=False)
        ticket_type, _order, ticket = issue(db, event, buyer, key="revoke-key-000001")
        entitlement = meal(db, event, organizer, ticket_type, requires_geofence=False)
        update_entitlement(db, event, entitlement, EntitlementUpdate(is_active=False), organizer)
        assert list_ticket_entitlements(db, ticket)[0]["status"] == "revoked"

    engine.dispose()


# ── Attribution ──────────────────────────────────────────────────────────────

def test_attendance_and_impact_belong_to_the_holder_not_the_purchaser(tmp_path):
    engine = make_db(tmp_path, "attribution.db")
    with Session(engine, expire_on_commit=False) as db:
        organizer, buyer, friend, _outsider, _community, event = setup(db, geofence=False)
        event.required_verification_methods = ["qr"]
        db.add(PointRule(source_type="attendance", points=30))
        db.commit()
        ticket_type = create_ticket_type(db, event.id, TicketTypeCreate(
            name="Regular", price=Decimal("1000.00"), quantity=4, max_per_user=1, max_per_order=4,
        ), organizer)
        order = create_order(db, event.id, OrderCreate(
            ticket_type_id=ticket_type.id, quantity=4, idempotency_key="attribution-key-1",
        ), buyer)
        settle(db, order, key="attribution-payment-key-01")
        tickets = db.query(Ticket).filter_by(order_id=order.id).order_by(Ticket.created_at).all()
        buyer_ticket = next(t for t in tickets if t.assignment_state == TicketAssignmentState.CLAIMED)
        shared = next(t for t in tickets if t.assignment_state == TicketAssignmentState.UNASSIGNED)
        _transfer, token = create_transfer(db, shared, buyer)
        claim_transfer(db, token, friend)

        assert validate_ticket(db, event.id, buyer_ticket.qr_token, organizer)[0] == "valid"
        assert validate_ticket(db, event.id, db.get(Ticket, shared.id).qr_token, organizer)[0] == "valid"
        rows = db.query(ImpactTransaction).filter_by(source_type="attendance").all()
        assert {row.user_id for row in rows} == {buyer.id, friend.id}
        assert {row.user_id for row in rows} != {buyer.id}
        assert db.query(ImpactTransaction).filter_by(user_id=buyer.id).count() == 1

    engine.dispose()


def test_repeated_scans_never_duplicate_impact(tmp_path):
    engine = make_db(tmp_path, "no-duplicate.db")
    with Session(engine, expire_on_commit=False) as db:
        organizer, buyer, _friend, _outsider, _community, event = setup(db, geofence=False)
        event.required_verification_methods = ["qr"]
        db.add(PointRule(source_type="attendance", points=15))
        db.commit()
        _type, _order, ticket = issue(db, event, buyer, key="dup-impact-key-1")
        assert validate_ticket(db, event.id, ticket.qr_token, organizer)[0] == "valid"
        assert validate_ticket(db, event.id, ticket.qr_token, organizer)[0] == "already_used"
        self_check_in(db, event.id, ticket.id, buyer, None)
        assert db.query(ImpactTransaction).filter_by(source_type="attendance").count() == 1
        assert db.query(Notification).filter_by(notification_type="check_in_confirmed").count() <= 1

    engine.dispose()


# ── Redemption authorization and committed-state decisions ───────────────────

def test_only_event_staff_may_validate_a_redemption(tmp_path):
    engine = make_db(tmp_path, "redeem-staff.db")
    with Session(engine, expire_on_commit=False) as db:
        organizer, buyer, friend, outsider, _community, event = setup(db)
        ticket_type, _order, ticket = issue(db, event, buyer, key="staff-key-000001")
        entitlement = meal(db, event, organizer, ticket_type)
        self_check_in(db, event.id, ticket.id, buyer, INSIDE)
        code = redeem_entitlement(db, event.id, ticket, entitlement.id, buyer, point=INSIDE)["code"]

        # Membership is not staffing: a fellow member and an unrelated user are both refused.
        for caller in (friend, outsider):
            with pytest.raises(HTTPException) as denied:
                validate_redemption(db, event.id, caller, code=code, point=INSIDE)
            assert denied.value.status_code == 403

        # Neither is an organizer of some other community.
        other = Community(organization_id=db.query(Organization).one().id,
                          name="Other Community", slug="other-community")
        db.add(other)
        db.flush()
        db.add(Membership(community_id=other.id, user_id=friend.id, role=MembershipRole.ORGANIZER))
        db.commit()
        with pytest.raises(HTTPException) as foreign:
            validate_redemption(db, event.id, friend, code=code, point=INSIDE)
        assert foreign.value.status_code == 403

        # The organizer who runs the event still can, and the credential burns exactly once.
        assert validate_redemption(db, event.id, organizer, code=code, point=INSIDE)["result"] == "redeemed"
        with pytest.raises(HTTPException) as repeat:
            validate_redemption(db, event.id, organizer, code=code, point=INSIDE)
        assert repeat.value.status_code == 409
        assert db.query(EntitlementRedemption).filter_by(status="redeemed").count() == 1

    engine.dispose()


def test_a_credential_redeemed_in_one_session_is_refused_in_the_next(tmp_path):
    """The single-use decision is made from committed state, not a cached identity map.

    True simultaneous scans are not reproducible on the SQLite test harness, so this asserts the
    property that makes the race safe: a second, independent session re-reads the credential and
    the locked entitlement row and observes the committed redemption instead of its own snapshot.
    """
    engine = make_db(tmp_path, "redeem-committed.db")
    with Session(engine, expire_on_commit=False) as db:
        organizer, buyer, _friend, _outsider, _community, event = setup(db, geofence=False)
        ticket_type, _order, ticket = issue(db, event, buyer, key="committed-key-001")
        entitlement = meal(db, event, organizer, ticket_type, requires_geofence=False)
        self_check_in(db, event.id, ticket.id, buyer, None)
        issued = redeem_entitlement(db, event.id, ticket, entitlement.id, buyer)
        event_id, ticket_id, code = event.id, ticket.id, issued["code"]
        assert validate_redemption(db, event_id, organizer, code=code)["remaining"] == 0

    with Session(engine, expire_on_commit=False) as db:
        with pytest.raises(HTTPException) as repeat:
            validate_redemption(db, event_id, organizer, code=code)
        assert repeat.value.status_code == 409
        assert db.query(EntitlementRedemption).filter_by(status="redeemed").count() == 1
        assert list_ticket_entitlements(db, db.get(Ticket, ticket_id))[0]["status"] == "redeemed"

    engine.dispose()


# ── Transfer single-use and lock ordering ────────────────────────────────────

def test_reissuing_a_transfer_retires_the_previous_link(tmp_path):
    engine = make_db(tmp_path, "transfer-reissue.db")
    with Session(engine, expire_on_commit=False) as db:
        _organizer, buyer, friend, _outsider, _community, event = setup(db, geofence=False)
        _type, _order, ticket = issue(db, event, buyer, key="reissue-key-00001")
        first, first_token = create_transfer(db, ticket, buyer)
        assert first.status == TransferStatus.PENDING
        second, second_token = create_transfer(db, ticket, buyer)
        assert second.status == TransferStatus.PENDING
        assert db.get(TicketTransfer, first.id).status == TransferStatus.CANCELLED

        # Only the newest link is live.
        with pytest.raises(HTTPException) as retired:
            claim_transfer(db, first_token, friend)
        assert retired.value.status_code == 409
        assert claim_transfer(db, second_token, friend).attendee_id == friend.id

    engine.dispose()


def test_a_claimed_link_cannot_be_claimed_again_from_another_session(tmp_path):
    """Claiming locks the ticket before the transfer row, so a second holder cannot slip in."""
    engine = make_db(tmp_path, "transfer-committed.db")
    with Session(engine, expire_on_commit=False) as db:
        _organizer, buyer, friend, outsider, _community, event = setup(db, geofence=False)
        _type, _order, ticket = issue(db, event, buyer, key="committed-transfer")
        _transfer, token = create_transfer(db, ticket, buyer)
        ticket_id = ticket.id
        assert claim_transfer(db, token, friend).attendee_id == friend.id

    with Session(engine, expire_on_commit=False) as db:
        with pytest.raises(HTTPException) as already:
            claim_transfer(db, token, outsider)
        assert already.value.status_code == 409
        # The ticket kept exactly one holder and the link is spent.
        assert db.get(Ticket, ticket_id).attendee_id == friend.id
        assert db.query(TicketTransfer).filter_by(status=TransferStatus.CLAIMED).count() == 1
        assert transfer_preview(db, token)["claimable"] is False

    engine.dispose()


def test_claiming_never_leaves_a_competing_pending_link(tmp_path):
    """Defends the invariant that a claimed ticket has no other live invitation.

    `create_transfer` retires siblings, so two pending rows can only exist if one predates that
    rule or was written out of band. Claiming must still resolve to a single live holder.
    """
    engine = make_db(tmp_path, "transfer-sibling.db")
    with Session(engine, expire_on_commit=False) as db:
        _organizer, buyer, friend, _outsider, _community, event = setup(db, geofence=False)
        _type, _order, ticket = issue(db, event, buyer, key="sibling-key-00001")
        _transfer, token = create_transfer(db, ticket, buyer)
        stale = TicketTransfer(
            ticket_id=ticket.id, created_by_id=buyer.id,
            claim_token_hash=hash_claim_token("stale-sibling-token"),
            status=TransferStatus.PENDING,
            expires_at=datetime.now(UTC) + TRANSFER_TTL,
        )
        db.add(stale)
        db.commit()

        claim_transfer(db, token, friend)
        assert db.get(TicketTransfer, stale.id).status == TransferStatus.CANCELLED
        assert db.query(TicketTransfer).filter_by(status=TransferStatus.PENDING).count() == 0
        assert db.get(Ticket, ticket.id).attendee_id == friend.id

    engine.dispose()


# ── Checkout lifecycle gate ──────────────────────────────────────────────────

def test_checkout_requires_a_published_event(tmp_path):
    engine = make_db(tmp_path, "checkout-lifecycle.db")
    with Session(engine, expire_on_commit=False) as db:
        _organizer, buyer, _friend, _outsider, _community, event = setup(db, geofence=False)
        _type, _order, ticket = issue(db, event, buyer, key="lifecycle-key-0001")
        self_check_in(db, event.id, ticket.id, buyer, None)
        for status in (EventStatus.DRAFT, EventStatus.CANCELLED, EventStatus.COMPLETED):
            event.status = status
            db.commit()
            with pytest.raises(HTTPException) as closed:
                self_check_out(db, event.id, ticket.id, buyer, None)
            assert closed.value.status_code == 409
        # Republishing reopens checkout, and the earlier refusals recorded nothing.
        event.status = EventStatus.PUBLISHED
        db.commit()
        state = self_check_out(db, event.id, ticket.id, buyer, None)
        assert state["checked_out_at"] is not None
        assert state["duration_seconds"] is not None

    engine.dispose()


def test_checkout_requires_the_feature_and_an_active_community(tmp_path):
    engine = make_db(tmp_path, "checkout-gates.db")
    with Session(engine, expire_on_commit=False) as db:
        _organizer, buyer, _friend, _outsider, _community, event = setup(db, geofence=False)
        _type, _order, ticket = issue(db, event, buyer, key="checkout-gate-0001")
        self_check_in(db, event.id, ticket.id, buyer, None)

        event.self_checkout_enabled = False
        db.commit()
        with pytest.raises(HTTPException) as disabled:
            self_check_out(db, event.id, ticket.id, buyer, None)
        assert disabled.value.status_code == 409

        event.self_checkout_enabled = True
        db.get(Community, event.community_id).is_active = False
        db.commit()
        with pytest.raises(HTTPException) as suspended:
            self_check_out(db, event.id, ticket.id, buyer, None)
        assert suspended.value.status_code == 403

    engine.dispose()
