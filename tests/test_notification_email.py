"""Email notification delivery tests."""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import Notification, NotificationPreference, User
from src.notifications.email import InMemoryEmailSender
from src.services.notification import notify


def test_notify_delivers_enabled_email_and_honors_preferences(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'email-notify.db'}")
    Base.metadata.create_all(engine)
    sender = InMemoryEmailSender()
    with Session(engine, expire_on_commit=False) as db:
        user = User(email="notify@example.com", password_hash="hash")
        db.add(user)
        db.flush()
        preference = NotificationPreference(user_id=user.id, email_enabled=True)
        db.add(preference)
        db.commit()
        notify(
            db,
            user.id,
            "event_reminder",
            "Event starts tomorrow",
            "Your event starts tomorrow.",
            {"event_id": "event-public-id"},
            email_sender=sender,
        )
        assert db.query(Notification).count() == 1
        assert sender.messages[-1].recipient == user.email
        assert sender.messages[-1].subject == "Event starts tomorrow"
        assert sender.messages[-1].body == "Your event starts tomorrow."

        preference.email_enabled = False
        db.commit()
        notify(db, user.id, "task_verified", "Task verified", "Your task was verified.", email_sender=sender)
        assert db.query(Notification).count() == 2
        assert len(sender.messages) == 1
    engine.dispose()
