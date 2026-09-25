"""Attendance anti-abuse checks."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import (
    Attendance,
    AttendanceStatus,
    PeerConfirmation,
    PeerConfirmationDecision,
    User,
)
from src.schemas.attendance import AttendanceCheckIn
from src.services.attendance import check_in, confirm_peer, evaluate_attendance_abuse
from tests.test_database import create_event_context


def test_low_accuracy_location_is_flagged_for_review(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'attendance-abuse.db'}")
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    _owner, _community, event = create_event_context(session)
    attendee = User(email="low-accuracy@example.com", password_hash="hash")
    session.add(attendee)
    session.flush()
    event.geofence_enabled = True
    event.geofence_radius_meters = 100
    if event.venue is None:
        from src.models import Venue

        event.venue = Venue(
            name="Venue",
            address="Address",
            latitude=Decimal("9.0"),
            longitude=Decimal("7.0"),
        )
    else:
        event.venue.latitude = Decimal("9.0")
        event.venue.longitude = Decimal("7.0")
    session.commit()
    attendance = check_in(
        session,
        event,
        attendee,
        AttendanceCheckIn(
            latitude=Decimal("9.0"),
            longitude=Decimal("7.0"),
            accuracy_meters=Decimal(500),
        ),
    )
    assert attendance.flagged_for_review
    assert "accuracy" in attendance.review_reason.lower()
    session.close()
    engine.dispose()


def test_duplicate_qr_verification_is_flagged_for_review(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'duplicate-qr.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        attendee, community, event = create_event_context(session)
        from src.models import Membership, MembershipRole
        session.add(Membership(community_id=community.id, user_id=attendee.id,
                               role=MembershipRole.ORGANIZER))
        attendance = Attendance(event_id=event.id, user_id=attendee.id, status=AttendanceStatus.CHECKED_IN)
        session.add(attendance); session.flush()
        from src.models import Ticket, TicketStatus, TicketType
        ticket_type = TicketType(event_id=event.id, name="Free", quantity=1)
        session.add(ticket_type); session.flush()
        ticket = Ticket(event_id=event.id, ticket_type_id=ticket_type.id, attendee_id=attendee.id,
                        status=TicketStatus.ACTIVE, public_id="DUPQR1", qr_token="duplicate-qr-token")
        session.add(ticket); session.commit()
        from src.services.attendance import qr_verify
        qr_verify(session, attendance, ticket, attendee)
        qr_verify(session, attendance, ticket, attendee)
        assert attendance.flagged_for_review
        assert "duplicate" in attendance.review_reason.lower()
    engine.dispose()


def test_impossible_location_transition_is_flagged_without_punishment(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'impossible-transition.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        attendee, community, first_event = create_event_context(session)
        from src.models import AttendanceVerification, Event, VerificationMethod
        second_event = Event(community_id=community.id, organizer_id=attendee.id, title="Second",
                             slug="second-transition", description="second", category="technology",
                             starts_at=datetime.now(UTC), ends_at=datetime.now(UTC), location_type="online",
                             online_url="https://example.com")
        session.add(second_event); session.flush()
        first = Attendance(event_id=first_event.id, user_id=attendee.id, status=AttendanceStatus.GPS_VERIFIED)
        second = Attendance(event_id=second_event.id, user_id=attendee.id, status=AttendanceStatus.GPS_VERIFIED)
        session.add_all([first, second]); session.flush()
        session.add_all([
            AttendanceVerification(attendance_id=first.id, method=VerificationMethod.GPS, is_valid=True,
                                   verified_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC), latitude=Decimal(9), longitude=Decimal(7)),
            AttendanceVerification(attendance_id=second.id, method=VerificationMethod.GPS, is_valid=True,
                                   verified_at=datetime(2026, 1, 1, 12, 1, tzinfo=UTC), latitude=Decimal(0), longitude=Decimal(0)),
        ])
        session.commit()
        evaluate_attendance_abuse(session, second)
        assert second.flagged_for_review
        assert "impossible_location_transition" in second.review_reason
        assert second.status == AttendanceStatus.GPS_VERIFIED
        evaluate_attendance_abuse(session, second)
        assert second.review_reason.count("impossible_location_transition") == 1
    engine.dispose()


def test_normal_location_transition_is_not_flagged(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'normal-transition.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        attendee, community, first_event = create_event_context(session)
        from src.models import AttendanceVerification, Event, VerificationMethod
        second_event = Event(community_id=community.id, organizer_id=attendee.id, title="Nearby",
                             slug="nearby-transition", description="nearby", category="technology",
                             starts_at=datetime.now(UTC), ends_at=datetime.now(UTC), location_type="online",
                             online_url="https://example.com")
        session.add(second_event); session.flush()
        first = Attendance(event_id=first_event.id, user_id=attendee.id, status=AttendanceStatus.GPS_VERIFIED)
        second = Attendance(event_id=second_event.id, user_id=attendee.id, status=AttendanceStatus.GPS_VERIFIED)
        session.add_all([first, second]); session.flush()
        session.add_all([
            AttendanceVerification(attendance_id=first.id, method=VerificationMethod.GPS, is_valid=True,
                                   verified_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC), latitude=Decimal(9), longitude=Decimal(7)),
            AttendanceVerification(attendance_id=second.id, method=VerificationMethod.GPS, is_valid=True,
                                   verified_at=datetime(2026, 1, 1, 13, 0, tzinfo=UTC), latitude=Decimal("9.001"), longitude=Decimal("7.001")),
        ])
        session.commit()
        evaluate_attendance_abuse(session, second)
        assert not second.flagged_for_review
    engine.dispose()


def test_reciprocal_peer_confirmation_is_flagged_not_auto_rejected(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'peer-abuse.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        _owner, _community, event = create_event_context(session)
        event.peer_confirmation_enabled = True
        first = User(email="first-peer@example.com", password_hash="hash")
        second = User(email="second-peer@example.com", password_hash="hash")
        session.add_all([first, second]); session.flush()
        session.add_all([
            Attendance(event_id=event.id, user_id=first.id, status=AttendanceStatus.CHECKED_IN),
            Attendance(event_id=event.id, user_id=second.id, status=AttendanceStatus.CHECKED_IN),
            PeerConfirmation(event_id=event.id, confirmer_id=second.id, subject_id=first.id,
                             decision=PeerConfirmationDecision.CONFIRMED,
                             submitted_at=datetime.now(UTC)),
        ])
        event.confirmations_required = 1
        session.commit()
        confirmation = confirm_peer(session, event, first, second.id, True)
        subject = session.query(Attendance).filter_by(event_id=event.id, user_id=second.id).one()
        assert confirmation.suspicious
        assert subject.flagged_for_review
        assert subject.status == AttendanceStatus.PEER_VERIFIED
    engine.dispose()


def test_repeated_peer_confirmations_are_flagged_for_review(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'repeated-peer-abuse.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        _owner, _community, event = create_event_context(session)
        event.peer_confirmation_enabled = True
        confirmer = User(email="repeat-peer@example.com", password_hash="hash")
        subjects = [
            User(email=f"repeat-subject-{index}@example.com", password_hash="hash")
            for index in range(4)
        ]
        session.add_all([confirmer, *subjects])
        session.flush()
        session.add_all(
            Attendance(
                event_id=event.id,
                user_id=user.id,
                status=AttendanceStatus.CHECKED_IN,
            )
            for user in [confirmer, *subjects]
        )
        session.commit()

        confirmations = [
            confirm_peer(session, event, confirmer, subject.id, True)
            for subject in subjects
        ]

        assert not any(item.suspicious for item in confirmations[:3])
        assert confirmations[3].suspicious
        reviewed = session.query(Attendance).filter_by(user_id=subjects[3].id).one()
        assert reviewed.flagged_for_review
        assert "repeated" in reviewed.review_reason.lower()
        assert reviewed.status == AttendanceStatus.PEER_VERIFIED
    engine.dispose()


def test_peer_verification_requires_distinct_confirmers_and_each_pair_is_single_use(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'distinct-peer-confirmations.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        _owner, _community, event = create_event_context(session)
        event.peer_confirmation_enabled = True
        event.confirmations_required = 2
        first = User(email="distinct-first@example.com", password_hash="hash")
        second = User(email="distinct-second@example.com", password_hash="hash")
        subject = User(email="distinct-subject@example.com", password_hash="hash")
        session.add_all([first, second, subject]); session.flush()
        session.add_all(
            Attendance(event_id=event.id, user_id=user.id, status=AttendanceStatus.CHECKED_IN)
            for user in (first, second, subject)
        )
        session.commit()

        confirm_peer(session, event, first, subject.id, True)
        subject_attendance = session.query(Attendance).filter_by(user_id=subject.id).one()
        assert subject_attendance.status == AttendanceStatus.CHECKED_IN
        with pytest.raises(HTTPException) as duplicate:
            confirm_peer(session, event, first, subject.id, True)
        assert duplicate.value.status_code == 409

        confirm_peer(session, event, second, subject.id, True)
        session.refresh(subject_attendance)
        assert subject_attendance.status == AttendanceStatus.PEER_VERIFIED
        confirmations = session.query(PeerConfirmation).filter_by(
            event_id=event.id, subject_id=subject.id,
            decision=PeerConfirmationDecision.CONFIRMED,
        ).all()
        assert {item.confirmer_id for item in confirmations} == {first.id, second.id}
    engine.dispose()
