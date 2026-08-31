"""Push notification delivery tests."""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import NotificationPreference, User
from src.notifications.push import InMemoryPushSender
from src.services.notification import notify


def test_notify_delivers_enabled_push_and_honors_preferences(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'push-notify.db'}")
    Base.metadata.create_all(engine)
    sender = InMemoryPushSender()
    with Session(engine, expire_on_commit=False) as db:
        user = User(email="push@example.com", password_hash="hash")
        db.add(user)
        db.flush()
        preference = NotificationPreference(user_id=user.id, push_enabled=True)
        db.add(preference)
        db.commit()
        notify(
            db,
            user.id,
            "badge_awarded",
            "New badge",
            "You earned a new badge.",
            {"badge_id": "badge-public-id"},
            push_sender=sender,
        )
        delivered = sender.messages[-1]
        assert delivered.user_id == user.id
        assert delivered.title == "New badge"
        assert delivered.data == {"badge_id": "badge-public-id"}

        preference.push_enabled = False
        db.commit()
        notify(db, user.id, "rank_reached", "New rank", "You reached a new rank.", push_sender=sender)
        assert len(sender.messages) == 1
    engine.dispose()
