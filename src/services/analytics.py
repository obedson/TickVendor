"""Tenant-scoped analytics aggregation service."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.authorization import require_community_role
from src.models import (
    Attendance,
    Community,
    Contribution,
    Event,
    ImpactTransaction,
    Membership,
    MembershipRole,
    Order,
    Payment,
    PaymentStatus,
    Task,
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
