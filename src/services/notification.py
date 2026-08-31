"""In-app notification and append-only audit helpers."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.models import AuditLog, Notification


def notify(db: Session, user_id, notification_type: str, title: str, message: str, payload=None):
    item = Notification(user_id=user_id, notification_type=notification_type, title=title,
                        message=message, payload=payload or {})
    db.add(item); db.commit(); return item


def audit(db: Session, *, actor_id, action: str, target_type: str, target_id=None,
          community_id=None, metadata=None):
    item = AuditLog(actor_id=actor_id, action=action, target_type=target_type,
                    target_id=target_id, community_id=community_id,
                    metadata_json=metadata or {}, occurred_at=datetime.now(UTC))
    db.add(item); db.commit(); return item
