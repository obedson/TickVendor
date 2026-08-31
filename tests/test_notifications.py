"""Notification and audit helper tests."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import AuditLog, Notification
from src.services.notification import audit, notify
from tests.test_database import create_event_context


def test_notifications_and_audit_are_persisted(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'notify.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        user, community, event = create_event_context(db)
        notify(db, user.id, "event", "Starts soon", "Your event starts tomorrow", {"event_id": str(event.id)})
        audit(db, actor_id=user.id, action="event.created", target_type="event",
              target_id=event.id, community_id=community.id)
        assert db.query(Notification).count() == 1
        assert db.query(AuditLog).one().action == "event.created"
    engine.dispose()
