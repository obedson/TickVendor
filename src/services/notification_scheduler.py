"""Scheduled useful notification generation."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models import Attendance, Event, EventStatus, Notification, Ticket, TicketStatus
from src.services.notification import notify


def generate_scheduled_notifications(db: Session, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    created = 0
    tomorrow_end = now + timedelta(hours=24)
    events = list(db.scalars(select(Event).where(
        Event.status == EventStatus.PUBLISHED, Event.deleted_at.is_(None),
        Event.starts_at > now, Event.starts_at <= tomorrow_end,
    )))
    for event in events:
        user_ids = set(db.scalars(select(Ticket.attendee_id).where(
            Ticket.event_id == event.id,
            Ticket.status.in_([TicketStatus.ACTIVE, TicketStatus.PAID]),
        )))
        for user_id in user_ids:
            key = f"event-reminder:{event.id}:{user_id}:{event.starts_at.date()}"
            if db.scalar(select(Notification.id).where(Notification.deduplication_key == key)) is None:
                notify(db, user_id, "event_reminder", "Event starts tomorrow",
                       "Your event starts tomorrow.", {"event_id": str(event.id)}, deduplication_key=key)
                created += 1
            if event.check_in_opens_at and event.check_in_opens_at <= now:
                attendance = db.scalar(select(Attendance.id).where(
                    Attendance.event_id == event.id, Attendance.user_id == user_id
                ))
                checkin_key = f"attendance-open:{event.id}:{user_id}"
                if attendance is None and db.scalar(select(Notification.id).where(
                        Notification.deduplication_key == checkin_key)) is None:
                    notify(db, user_id, "attendance_open", "Attendance is open",
                           "Attendance is now open.", {"event_id": str(event.id)},
                           deduplication_key=checkin_key)
                    created += 1
    return created
