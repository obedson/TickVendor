"""Scheduled notification tests."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import EventStatus, Notification, Ticket, TicketStatus, TicketType, User
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
