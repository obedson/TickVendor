"""Event engagement analytics service tests."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import (
    Attendance,
    AttendanceStatus,
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
        db.commit()
        summary = event_summary(db, event.id, user)
        assert summary["tickets"] == 1
        assert summary["checked_in"] == 1
        assert summary["verified"] == 1
    engine.dispose()
