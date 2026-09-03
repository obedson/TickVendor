"""Scheduled useful notification generation."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models import (
    Attendance,
    AttendanceStatus,
    Event,
    EventStatus,
    ImpactTransaction,
    ImpactTransactionStatus,
    Milestone,
    MilestoneAward,
    MilestoneRequirement,
    Notification,
    PeerConfirmation,
    Ticket,
    TicketStatus,
)
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
                       "Your event starts tomorrow.", {"event_id": str(event.id)}, community_id=event.community_id, deduplication_key=key)
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
                           community_id=event.community_id, deduplication_key=checkin_key)
                    created += 1

    proximity_requirements = db.execute(
        select(Milestone, MilestoneRequirement)
        .join(MilestoneRequirement, MilestoneRequirement.milestone_id == Milestone.id)
        .where(
            Milestone.is_active.is_(True),
            MilestoneRequirement.metric == "impact_points",
            MilestoneRequirement.operator == ">=",
        )
    ).all()
    for milestone, requirement in proximity_requirements:
        point_rows = db.execute(
            select(ImpactTransaction.user_id, func.sum(ImpactTransaction.points))
            .where(
                ImpactTransaction.community_id == milestone.community_id,
                ImpactTransaction.status == ImpactTransactionStatus.POSTED,
            )
            .group_by(ImpactTransaction.user_id)
        ).all()
        for user_id, points in point_rows:
            remaining = requirement.threshold - points
            already_awarded = db.scalar(select(MilestoneAward.id).where(
                MilestoneAward.milestone_id == milestone.id,
                MilestoneAward.user_id == user_id,
            ))
            key = f"milestone-proximity:{milestone.id}:{user_id}:{requirement.threshold}"
            if 0 < remaining <= 20 and already_awarded is None and db.scalar(
                select(Notification.id).where(Notification.deduplication_key == key)
            ) is None:
                notify(
                    db,
                    user_id,
                    "milestone_proximity",
                    "Milestone within reach",
                    f"You're {remaining} Impact Points away from {milestone.name}.",
                    {"milestone_id": str(milestone.id), "points_remaining": remaining},
                    community_id=milestone.community_id, deduplication_key=key,
                )
                created += 1

    peer_events = db.scalars(select(Event).where(
        Event.peer_confirmation_enabled.is_(True),
        Event.ends_at <= now,
        Event.deleted_at.is_(None),
    ))
    eligible_statuses = [
        AttendanceStatus.GPS_VERIFIED,
        AttendanceStatus.QR_VERIFIED,
        AttendanceStatus.PEER_VERIFIED,
        AttendanceStatus.ORGANIZER_VERIFIED,
    ]
    for event in peer_events:
        attendee_ids = list(db.scalars(select(Attendance.user_id).where(
            Attendance.event_id == event.id,
            Attendance.status.in_(eligible_statuses),
        )))
        if len(attendee_ids) < 2:
            continue
        for user_id in attendee_ids:
            submitted = db.scalar(select(PeerConfirmation.id).where(
                PeerConfirmation.event_id == event.id,
                PeerConfirmation.confirmer_id == user_id,
            ))
            key = f"peer-confirmation-pending:{event.id}:{user_id}"
            if submitted is None and db.scalar(
                select(Notification.id).where(Notification.deduplication_key == key)
            ) is None:
                notify(
                    db,
                    user_id,
                    "peer_confirmation_pending",
                    "Attendance confirmations waiting",
                    "You have attendance confirmations waiting.",
                    {"event_id": str(event.id)},
                    community_id=event.community_id, deduplication_key=key,
                )
                created += 1
    return created
