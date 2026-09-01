"""Tenant-scoped analytics aggregation service."""

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.authorization import require_community_role
from src.models import (
    Attendance,
    AttendanceStatus,
    Badge,
    BadgeAward,
    Community,
    Contribution,
    Event,
    ImpactTransaction,
    ImpactTransactionStatus,
    Membership,
    MembershipRole,
    MembershipStatus,
    Milestone,
    MilestoneAward,
    Order,
    Payment,
    PaymentStatus,
    Task,
    TaskAssignment,
    TaskAssignmentStatus,
    Ticket,
    User,
)
from src.services.recognition import current_rank


def community_summary(db: Session, community_id, user: User) -> dict[str, object]:
    require_community_role(db, community_id, user, MembershipRole.ADMIN)
    community = db.get(Community, community_id)
    event_ids = select(Event.id).where(Event.community_id == community_id)
    active_user_ids = list(db.scalars(select(Membership.user_id).where(
        Membership.community_id == community_id,
        Membership.status == MembershipStatus.ACTIVE,
    )))
    badge_rows = db.execute(
        select(Badge.name, func.count(BadgeAward.id))
        .join(BadgeAward, BadgeAward.badge_id == Badge.id)
        .where(Badge.community_id == community_id, BadgeAward.revoked_at.is_(None))
        .group_by(Badge.id, Badge.name)
        .order_by(Badge.name)
    ).all()
    rank_counts: dict[str, int] = {}
    for member_id in active_user_ids:
        rank = current_rank(db, member_id, community_id)
        if rank is not None:
            rank_counts[rank.name] = rank_counts.get(rank.name, 0) + 1
    attendance_rows = db.execute(
        select(func.strftime("%Y-%m", Attendance.checked_in_at), func.count())
        .where(
            Attendance.event_id.in_(event_ids),
            Attendance.checked_in_at.is_not(None),
            Attendance.status.notin_([AttendanceStatus.NOT_CHECKED_IN, AttendanceStatus.REJECTED]),
        )
        .group_by(func.strftime("%Y-%m", Attendance.checked_in_at))
        .order_by(func.strftime("%Y-%m", Attendance.checked_in_at))
    ).all()
    cutoff = datetime.now(UTC) - timedelta(days=30)
    eligible_ids = list(db.scalars(select(Membership.user_id).where(
        Membership.community_id == community_id,
        Membership.status == MembershipStatus.ACTIVE,
        Membership.joined_at <= cutoff,
    )))
    retained = db.scalar(select(func.count(func.distinct(Attendance.user_id))).where(
        Attendance.user_id.in_(eligible_ids),
        Attendance.event_id.in_(event_ids),
        Attendance.checked_in_at >= cutoff,
        Attendance.status.notin_([AttendanceStatus.NOT_CHECKED_IN, AttendanceStatus.REJECTED]),
    )) if eligible_ids else 0
    return {
        "community_id": str(community.id),
        "members": db.scalar(select(func.count()).select_from(Membership).where(Membership.community_id == community_id)),
        "active_members": len(active_user_ids),
        "events": db.scalar(select(func.count()).select_from(Event).where(Event.community_id == community_id)),
        "tickets": db.scalar(select(func.count()).select_from(Ticket).where(Ticket.event_id.in_(event_ids))),
        "attendance": db.scalar(select(func.count()).select_from(Attendance).where(Attendance.event_id.in_(event_ids))),
        "tasks": db.scalar(select(func.count()).select_from(Task).where(Task.community_id == community_id)),
        "contributions": db.scalar(select(func.count()).select_from(Contribution).where(Contribution.community_id == community_id)),
        "impact_points": db.scalar(select(func.coalesce(func.sum(ImpactTransaction.points), 0)).where(
            ImpactTransaction.community_id == community_id
        )),
        "revenue": str(db.scalar(select(func.coalesce(func.sum(Payment.amount), 0))
            .join(Order, Payment.order_id == Order.id).join(Event, Order.event_id == Event.id)
            .where(Event.community_id == community_id, Payment.status == PaymentStatus.SUCCESSFUL))),
        "badge_distribution": [{"name": name, "awards": awards} for name, awards in badge_rows],
        "rank_distribution": [
            {"name": name, "members": members} for name, members in sorted(rank_counts.items())
        ],
        "participation_trends": [
            {"period": period, "attendances": count} for period, count in attendance_rows
        ],
        "retention": {
            "eligible_members": len(eligible_ids),
            "retained_members": retained,
            "rate": round(retained / len(eligible_ids), 4) if eligible_ids else 0.0,
        },
    }


def organizer_summary(db: Session, user: User) -> dict[str, object]:
    event_ids = select(Event.id).where(Event.organizer_id == user.id, Event.deleted_at.is_(None))
    community_ids = select(Event.community_id).where(
        Event.organizer_id == user.id, Event.deleted_at.is_(None)
    )
    badge_distribution = db.execute(
        select(Badge.name, func.count(BadgeAward.id))
        .join(BadgeAward, BadgeAward.badge_id == Badge.id)
        .where(Badge.community_id.in_(community_ids), BadgeAward.revoked_at.is_(None))
        .group_by(Badge.id, Badge.name)
        .order_by(Badge.name)
    ).all()
    milestone_distribution = db.execute(
        select(Milestone.name, func.count(MilestoneAward.id))
        .join(MilestoneAward, MilestoneAward.milestone_id == Milestone.id)
        .where(Milestone.community_id.in_(community_ids))
        .group_by(Milestone.id, Milestone.name)
        .order_by(Milestone.name)
    ).all()
    top = db.execute(select(ImpactTransaction.user_id, func.sum(ImpactTransaction.points).label("score"))
        .where(ImpactTransaction.event_id.in_(event_ids),
               ImpactTransaction.status == ImpactTransactionStatus.POSTED)
        .group_by(ImpactTransaction.user_id).order_by(func.sum(ImpactTransaction.points).desc())
        .limit(10)).all()
    return {
        "upcoming_events": db.scalar(select(func.count()).select_from(Event).where(
            Event.organizer_id == user.id, Event.starts_at >= func.now(), Event.deleted_at.is_(None))),
        "total_events": db.scalar(select(func.count()).select_from(Event).where(
            Event.organizer_id == user.id, Event.deleted_at.is_(None))),
        "ticket_sales": db.scalar(select(func.count()).select_from(Ticket).where(
            Ticket.event_id.in_(event_ids))),
        "revenue": str(db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).join(
            Order, Payment.order_id == Order.id).where(
            Order.event_id.in_(event_ids), Payment.status == PaymentStatus.SUCCESSFUL))),
        "registrations": db.scalar(select(func.count()).select_from(Order).where(
            Order.event_id.in_(event_ids))),
        "attendance": db.scalar(select(func.count()).select_from(Attendance).where(
            Attendance.event_id.in_(event_ids))),
        "verified_attendance": db.scalar(select(func.count()).select_from(Attendance).where(
            Attendance.event_id.in_(event_ids), Attendance.status.notin_([
                AttendanceStatus.NOT_CHECKED_IN, AttendanceStatus.CHECKED_IN,
                AttendanceStatus.REJECTED]))),
        "pending_tasks": db.scalar(select(func.count()).select_from(TaskAssignment).where(
            TaskAssignment.task_id.in_(select(Task.id).where(Task.event_id.in_(event_ids))),
            TaskAssignment.status.in_([TaskAssignmentStatus.ASSIGNED, TaskAssignmentStatus.SUBMITTED]))),
        "contributions": db.scalar(select(func.count()).select_from(Contribution).where(
            Contribution.event_id.in_(event_ids))),
        "engagement": db.scalar(select(func.coalesce(func.sum(ImpactTransaction.points), 0)).where(
            ImpactTransaction.event_id.in_(event_ids),
            ImpactTransaction.status == ImpactTransactionStatus.POSTED)),
        "top_participants": [{"user_id": str(user_id), "score": score}
                             for user_id, score in top],
        "achievement_distribution": {
            "badges": [{"name": name, "awards": awards} for name, awards in badge_distribution],
            "milestones": [
                {"name": name, "awards": awards} for name, awards in milestone_distribution
            ],
        },
    }


def event_summary(db: Session, event_id, user: User) -> dict[str, object]:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    require_community_role(db, event.community_id, user, MembershipRole.ORGANIZER)
    verified_states = [
        "GPS_VERIFIED",
        "QR_VERIFIED",
        "PEER_VERIFIED",
        "ORGANIZER_VERIFIED",
    ]
    attendance_total = db.scalar(
        select(func.count()).select_from(Attendance).where(Attendance.event_id == event_id)
    )
    verified = db.scalar(
        select(func.count()).select_from(Attendance).where(
            Attendance.event_id == event_id,
            Attendance.status.in_(verified_states),
        )
    )
    return {
        "event_id": str(event.id),
        "tickets": db.scalar(
            select(func.count()).select_from(Ticket).where(Ticket.event_id == event_id)
        ),
        "checked_in": attendance_total,
        "verified": verified,
        "tasks": db.scalar(
            select(func.count()).select_from(Task).where(Task.event_id == event_id)
        ),
        "contribution_amount": str(db.scalar(
            select(func.coalesce(func.sum(Contribution.amount), 0)).where(
                Contribution.event_id == event_id
            )
        )),
        "badges_earned": db.scalar(
            select(func.count()).select_from(BadgeAward).where(
                BadgeAward.event_id == event_id, BadgeAward.revoked_at.is_(None)
            )
        ),
        "impact_points": db.scalar(
            select(func.coalesce(func.sum(ImpactTransaction.points), 0)).where(
                ImpactTransaction.event_id == event_id
            )
        ),
    }
