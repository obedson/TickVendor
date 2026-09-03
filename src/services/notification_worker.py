"""Claim and deliver scheduled notifications with local-safe idempotency."""

from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.models import (
    NotificationPreference,
    NotificationRule,
    ScheduledNotification,
    ScheduledNotificationStatus,
)
from src.monitoring import emit


class ScheduledSender(Protocol):
    def send(self, user_id, notification_type: str, title: str, message: str, payload: dict) -> None: ...


def process_scheduled_notifications(db: Session, sender: ScheduledSender, *, now: datetime | None = None, batch_size: int = 100) -> int:
    now = now or datetime.now(UTC)
    due = list(db.scalars(select(ScheduledNotification).where(
        ScheduledNotification.status.in_([ScheduledNotificationStatus.PENDING, ScheduledNotificationStatus.RETRYABLE]),
        ScheduledNotification.scheduled_at <= now,
        (ScheduledNotification.next_attempt_at.is_(None)) | (ScheduledNotification.next_attempt_at <= now),
    ).order_by(ScheduledNotification.scheduled_at, ScheduledNotification.id).limit(batch_size)))
    delivered = 0
    for item in due:
        claimed = db.execute(update(ScheduledNotification).where(
            ScheduledNotification.id == item.id,
            ScheduledNotification.status.in_([ScheduledNotificationStatus.PENDING, ScheduledNotificationStatus.RETRYABLE]),
        ).values(status=ScheduledNotificationStatus.PROCESSING, claimed_at=now, attempt_count=ScheduledNotification.attempt_count + 1)).rowcount
        db.commit()
        if claimed != 1:
            continue
        preference = db.scalar(select(NotificationPreference).where(NotificationPreference.user_id == item.user_id))
        rule = db.scalar(select(NotificationRule).where(
            NotificationRule.community_id == item.community_id,
            NotificationRule.notification_type == item.notification_type,
            NotificationRule.is_active.is_(True),
        )) if item.community_id else None
        muted = preference and item.notification_type in preference.muted_types
        channels_enabled = (
            (rule is None or rule.in_app_enabled) and (preference is None or preference.in_app_enabled)
            or (rule is None or rule.email_enabled) and preference is not None and preference.email_enabled
            or (rule is None or rule.push_enabled) and preference is not None and preference.push_enabled
        )
        if muted or not channels_enabled:
            db.execute(update(ScheduledNotification).where(ScheduledNotification.id == item.id).values(
                status=ScheduledNotificationStatus.DELIVERED, delivered_at=now))
            db.commit(); delivered += 1; continue
        try:
            sender.send(item.user_id, item.notification_type, item.title, item.message, item.payload)
        except Exception as exc:  # noqa: BLE001 - adapter failures must become retry state
            emit("notification_worker_failure", notification_id=str(item.id),
                 error_type=type(exc).__name__)
            current = db.get(ScheduledNotification, item.id)
            terminal = current.attempt_count >= current.max_attempts
            db.execute(update(ScheduledNotification).where(ScheduledNotification.id == item.id).values(
                status=ScheduledNotificationStatus.FAILED if terminal else ScheduledNotificationStatus.RETRYABLE,
                next_attempt_at=None if terminal else now + timedelta(minutes=5 * current.attempt_count),
                last_error=str(exc)[:1000]))
            db.commit(); continue
        db.execute(update(ScheduledNotification).where(ScheduledNotification.id == item.id).values(
            status=ScheduledNotificationStatus.DELIVERED, delivered_at=now, last_error=None))
        db.commit(); delivered += 1
    return delivered
