"""Event engagement analytics service tests."""

from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import (
    Attendance,
    AttendanceStatus,
    Badge,
    BadgeAward,
    Contribution,
    ContributionType,
    Membership,
    MembershipRole,
    Ticket,
    TicketStatus,
    TicketType,
)
from src.services.analytics import event_summary
from tests.test_database import create_event_context


def test_event_summary_counts_tickets_and_attendance(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'event-summary.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        user, _community, event = create_event_context(db)
        db.add(
            Membership(
                community_id=event.community_id,
                user_id=user.id,
                role=MembershipRole.ORGANIZER,
            )
        )
        ticket_type = TicketType(event_id=event.id, name="Free", price=0, quantity=10)
        db.add(ticket_type)
        db.flush()
        db.add_all(
            [
                Ticket(
                    public_id="SUMMARY-TICKET",
                    qr_token="s" * 48,
                    event_id=event.id,
                    ticket_type_id=ticket_type.id,
                    attendee_id=user.id,
                    status=TicketStatus.ACTIVE,
                ),
                Attendance(
                    event_id=event.id,
                    user_id=user.id,
                    status=AttendanceStatus.GPS_VERIFIED,
                ),
            ]
        )
        badge = Badge(community_id=event.community_id, name="Event Badge", slug="event-badge",
                      category="attendance")
        db.add(badge); db.flush()
        db.add_all([
            Contribution(community_id=event.community_id, event_id=event.id,
                         contributor_id=user.id, contribution_type=ContributionType.MONETARY,
                         amount=2500, currency="NGN", purpose="Event support",
                         occurred_at=datetime.now(UTC)),
            BadgeAward(badge_id=badge.id, event_id=event.id, user_id=user.id,
                       idempotency_key="event-badge-award", awarded_at=datetime.now(UTC)),
        ])
        db.commit()
        summary = event_summary(db, event.id, user)
        assert summary["tickets"] == 1
        assert summary["checked_in"] == 1
        assert summary["verified"] == 1
        assert summary["contribution_amount"] == "2500.00"
        assert summary["badges_earned"] == 1
    engine.dispose()
