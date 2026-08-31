"""In-app notification and append-only audit helpers."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.models import AuditLog, Notification, NotificationPreference, User
from src.notifications.email import EmailSender, get_email_sender
from src.notifications.push import PushSender, get_push_sender


def notify(
    db: Session,
    user_id,
    notification_type: str,
    title: str,
    message: str,
    payload=None,
    *,
    email_sender: EmailSender | None = None,
    push_sender: PushSender | None = None,
):
    preference = db.query(NotificationPreference).filter_by(user_id=user_id).one_or_none()
    if preference and notification_type in preference.muted_types:
        return None
    item = None
    if preference is None or preference.in_app_enabled:
        item = Notification(user_id=user_id, notification_type=notification_type, title=title,
                            message=message, payload=payload or {})
        db.add(item)
    if preference and preference.email_enabled:
        user = db.get(User, user_id)
        if user is not None:
            (email_sender or get_email_sender()).send(user.email, title, message)
    if preference and preference.push_enabled:
        (push_sender or get_push_sender()).send(user_id, title, message, payload or {})
    db.commit()
    return item


def audit(db: Session, *, actor_id, action: str, target_type: str, target_id=None,
          community_id=None, metadata=None):
    item = AuditLog(actor_id=actor_id, action=action, target_type=target_type,
                    target_id=target_id, community_id=community_id,
                    metadata_json=metadata or {}, occurred_at=datetime.now(UTC))
    db.add(item); db.commit(); return item
