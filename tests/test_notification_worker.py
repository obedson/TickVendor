"""Scheduled notification worker behavior."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import (
    NotificationPreference,
    ScheduledNotification,
    ScheduledNotificationStatus,
    User,
)
from src.services.notification_worker import process_scheduled_notifications


class LocalSender:
    def __init__(self, failures=0):
        self.messages = []
        self.failures = failures

    def send(self, user_id, notification_type, title, message, payload):
        if self.failures:
            self.failures -= 1
            raise RuntimeError("temporary delivery failure")
        self.messages.append((user_id, notification_type, title, message, payload))


class FailingSender(LocalSender):
    pass


def setup(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'notification-worker.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email="worker@example.com", password_hash="hash")
        db.add(user); db.commit(); user_id = user.id
    return engine, user_id


def test_due_work_delivers_once_and_replay_is_skipped(tmp_path):
    engine, user_id = setup(tmp_path)
    sender = LocalSender()
    now = datetime.now(UTC)
    with Session(engine) as db:
        work = ScheduledNotification(user_id=user_id, community_id=None, notification_type="reminder",
                                     title="Reminder", message="Do it", payload={},
                                     idempotency_key="worker-once", scheduled_at=now - timedelta(minutes=1))
        db.add(work); db.commit()
        assert process_scheduled_notifications(db, sender, now=now) == 1
        assert process_scheduled_notifications(db, sender, now=now) == 0
        assert len(sender.messages) == 1
        assert db.get(ScheduledNotification, work.id).status == ScheduledNotificationStatus.DELIVERED
    engine.dispose()


def test_future_work_and_muted_preference_are_not_delivered(tmp_path):
    engine, user_id = setup(tmp_path)
    sender = LocalSender(); now = datetime.now(UTC)
    with Session(engine) as db:
        future = ScheduledNotification(user_id=user_id, notification_type="future", title="Future", message="later", payload={}, idempotency_key="future", scheduled_at=now + timedelta(hours=1))
        db.add(future); db.commit()
        assert process_scheduled_notifications(db, sender, now=now) == 0
        assert sender.messages == []
        db.add(NotificationPreference(user_id=user_id, in_app_enabled=False))
        muted = ScheduledNotification(user_id=user_id, notification_type="muted", title="Muted",
                                      message="hidden", payload={}, idempotency_key="muted",
                                      scheduled_at=now - timedelta(minutes=1))
        db.add(muted); db.commit()
        assert process_scheduled_notifications(db, sender, now=now) == 1
        assert sender.messages == []
    engine.dispose()


def test_transient_failure_retries_with_backoff(tmp_path):
    engine, user_id = setup(tmp_path)
    sender = LocalSender(failures=1); now = datetime.now(UTC)
    with Session(engine) as db:
        work = ScheduledNotification(user_id=user_id, notification_type="retry", title="Retry", message="again", payload={}, idempotency_key="retry", scheduled_at=now - timedelta(minutes=1), max_attempts=3)
        db.add(work); db.commit()
        assert process_scheduled_notifications(db, sender, now=now) == 0
        db.refresh(work)
        assert work.status == ScheduledNotificationStatus.RETRYABLE and work.attempt_count == 1
        assert process_scheduled_notifications(db, sender, now=now + timedelta(minutes=6)) == 1
        assert work.status == ScheduledNotificationStatus.DELIVERED
    engine.dispose()


def test_max_attempts_becomes_terminal_failure(tmp_path):
    engine, user_id = setup(tmp_path); sender = LocalSender(failures=1); now = datetime.now(UTC)
    with Session(engine) as db:
        work = ScheduledNotification(user_id=user_id, notification_type="terminal", title="Terminal",
                                     message="fail", payload={}, idempotency_key="terminal",
                                     scheduled_at=now - timedelta(minutes=1), max_attempts=1)
        db.add(work); db.commit()
        assert process_scheduled_notifications(db, sender, now=now) == 0
        db.refresh(work)
        assert work.status == ScheduledNotificationStatus.FAILED
        assert process_scheduled_notifications(db, sender, now=now + timedelta(days=1)) == 0
    engine.dispose()


def test_processing_work_cannot_be_claimed_by_another_worker(tmp_path):
    engine, user_id = setup(tmp_path); now = datetime.now(UTC); sender = LocalSender()
    with Session(engine) as db:
        work = ScheduledNotification(user_id=user_id, notification_type="claimed", title="Claimed",
                                     message="held", payload={}, idempotency_key="claimed",
                                     scheduled_at=now - timedelta(minutes=1),
                                     status=ScheduledNotificationStatus.PROCESSING, claimed_at=now)
        db.add(work); db.commit()
        assert process_scheduled_notifications(db, sender, now=now) == 0
        assert sender.messages == []
    engine.dispose()
