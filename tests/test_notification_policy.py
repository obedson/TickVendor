"""Community notification rule dispatch tests."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import (
    Community,
    Notification,
    NotificationPreference,
    NotificationRule,
    ScheduledNotification,
    ScheduledNotificationStatus,
    User,
)
from src.notifications.email import InMemoryEmailSender
from src.services.notification import notify
from src.services.notification_worker import process_scheduled_notifications
from tests.test_database import create_event_context


def test_community_rule_controls_channels_without_overriding_user_opt_out(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'notification-policy.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user, community, _event = create_event_context(db)
        db.add(NotificationPreference(user_id=user.id, email_enabled=True))
        db.add(NotificationRule(community_id=community.id, notification_type="task_verified", in_app_enabled=False, email_enabled=True))
        db.commit()
        sender = InMemoryEmailSender()
        notify(db, user.id, "task_verified", "Verified", "Done", community_id=community.id, email_sender=sender)
        assert db.query(Notification).count() == 0
        assert len(sender.messages) == 1
        db.query(NotificationRule).one().email_enabled = False
        db.commit()
        notify(db, user.id, "task_verified", "Disabled", "Suppressed", community_id=community.id, email_sender=sender)
        assert len(sender.messages) == 1
    engine.dispose()


def test_scheduled_worker_applies_community_rule_and_keeps_other_tenant_isolated(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'notification-worker-policy.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user_a, community_a, _event = create_event_context(db)
        user_b = User(email="policy-b@example.com", password_hash="hash")
        db.add(user_b); db.flush()
        other = Community(organization_id=community_a.organization_id, name="Other", slug="policy-other")
        db.add(other); db.flush()
        db.add(NotificationRule(community_id=community_a.id, notification_type="reminder", in_app_enabled=False))
        now = datetime.now(UTC)
        db.add_all([
            ScheduledNotification(user_id=user_a.id, community_id=community_a.id, notification_type="reminder", title="A", message="A", payload={}, idempotency_key="policy-a", scheduled_at=now - timedelta(minutes=1)),
            ScheduledNotification(user_id=user_b.id, community_id=other.id, notification_type="reminder", title="B", message="B", payload={}, idempotency_key="policy-b", scheduled_at=now - timedelta(minutes=1)),
        ])
        db.commit()
        class Sender:
            def __init__(self): self.sent = []
            def send(self, *args): self.sent.append(args)
        sender = Sender()
        assert process_scheduled_notifications(db, sender, now=now) == 2
        assert len(sender.sent) == 1 and sender.sent[0][0] == user_b.id
        assert db.query(ScheduledNotification).filter_by(status=ScheduledNotificationStatus.DELIVERED).count() == 2
    engine.dispose()
