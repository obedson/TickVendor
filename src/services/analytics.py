"""Tenant-scoped analytics aggregation service."""

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.authorization import require_community_role
from src.models import (
    Attendance,
    AttendanceStatus,
    BadgeAward,
    Community,
    Contribution,
    Event,
    ImpactTransaction,
    ImpactTransactionStatus,
    Membership,
    MembershipRole,
    Order,
    Payment,
    PaymentStatus,
    Task,
    TaskAssignment,
    TaskAssignmentStatus,
    Ticket,
    User,
)


def community_summary(db: Session, community_id, user: User) -> dict[str, object]:
    require_community_role(db, community_id, user, MembershipRole.ADMIN)
    community = db.get(Community, community_id)
    event_ids = select(Event.id).where(Event.community_id == community_id)
    return {
        "community_id": str(community.id),
        "members": db.scalar(select(func.count()).select_from(Membership).where(Membership.community_id == community_id)),
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
    }


def organizer_summary(db: Session, user: User) -> dict[str, object]:
    event_ids = select(Event.id).where(Event.organizer_id == user.id, Event.deleted_at.is_(None))
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
