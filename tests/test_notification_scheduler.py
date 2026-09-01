"""Scheduled notification tests."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import (
    Attendance,
    AttendanceStatus,
    EventStatus,
    ImpactTransaction,
    ImpactTransactionStatus,
    Milestone,
    MilestoneRequirement,
    Notification,
    Ticket,
    TicketStatus,
    TicketType,
    User,
)
from src.services.notification_scheduler import generate_scheduled_notifications
from tests.test_database import create_event_context


def test_event_and_attendance_reminders_are_idempotent(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'scheduled.db'}");Base.metadata.create_all(engine)
    with Session(engine,expire_on_commit=False) as db:
        _owner,_community,event=create_event_context(db);attendee=User(email='reminder@example.com',password_hash='hash');db.add(attendee);db.flush();ticket_type=TicketType(event_id=event.id,name='Free',price=0,quantity=1);db.add(ticket_type);db.flush();now=datetime.now(UTC)
        event.status=EventStatus.PUBLISHED;event.starts_at=now+timedelta(hours=20);event.ends_at=now+timedelta(hours=22);event.check_in_opens_at=now-timedelta(minutes=1)
        db.add(Ticket(public_id='REMINDER-TICKET',qr_token='r'*48,event_id=event.id,ticket_type_id=ticket_type.id,attendee_id=attendee.id,status=TicketStatus.ACTIVE));db.commit()
        assert generate_scheduled_notifications(db,now)==2
        assert generate_scheduled_notifications(db,now)==0
        assert {item.notification_type for item in db.query(Notification)}=={'event_reminder','attendance_open'}
    engine.dispose()


def test_milestone_proximity_and_peer_confirmation_prompts_are_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'scheduled-prompts.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        _owner, community, event = create_event_context(db)
        attendee = User(email="prompt-attendee@example.com", password_hash="hash")
        peer = User(email="prompt-peer@example.com", password_hash="hash")
        db.add_all([attendee, peer])
        db.flush()
        now = datetime.now(UTC)
        event.status = EventStatus.PUBLISHED
        event.starts_at = now - timedelta(hours=3)
        event.ends_at = now - timedelta(hours=1)
        event.peer_confirmation_enabled = True
        db.add_all([
            Attendance(
                event_id=event.id,
                user_id=attendee.id,
                status=AttendanceStatus.GPS_VERIFIED,
            ),
            Attendance(
                event_id=event.id,
                user_id=peer.id,
                status=AttendanceStatus.QR_VERIFIED,
            ),
            ImpactTransaction(
                idempotency_key="prompt-points",
                user_id=attendee.id,
                community_id=community.id,
                points=280,
                source_type="attendance",
                reason="Progress",
                status=ImpactTransactionStatus.POSTED,
            ),
        ])
        milestone = Milestone(
            community_id=community.id,
            name="Community Builder",
            slug="community-builder",
        )
        db.add(milestone)
        db.flush()
        db.add(MilestoneRequirement(
            milestone_id=milestone.id,
            metric="impact_points",
            operator=">=",
            threshold=300,
        ))
        db.commit()

        assert generate_scheduled_notifications(db, now) == 3
        assert generate_scheduled_notifications(db, now) == 0
        notifications = db.query(Notification).all()
        assert {item.notification_type for item in notifications} == {
            "milestone_proximity",
            "peer_confirmation_pending",
        }
        proximity = next(
            item for item in notifications if item.notification_type == "milestone_proximity"
        )
        assert proximity.user_id == attendee.id
        assert "20 Impact Points" in proximity.message
    engine.dispose()
