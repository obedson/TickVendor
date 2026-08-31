"""Recognition qualification engine for configurable milestones, ranks, and badges."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models import (
    Attendance,
    AttendanceStatus,
    Badge,
    BadgeAward,
    ImpactTransaction,
    ImpactTransactionStatus,
    Milestone,
    MilestoneRequirement,
    Rank,
    TaskAssignment,
    TaskAssignmentStatus,
)


def user_metrics(db: Session, user_id, community_id) -> dict[str, int]:
    return {
        "impact_points": db.scalar(select(func.coalesce(func.sum(ImpactTransaction.points), 0)).where(
            ImpactTransaction.user_id == user_id, ImpactTransaction.community_id == community_id,
            ImpactTransaction.status == ImpactTransactionStatus.POSTED,
        )),
        "attendance_count": db.scalar(select(func.count()).select_from(Attendance).where(
            Attendance.user_id == user_id,
            Attendance.status.notin_([AttendanceStatus.NOT_CHECKED_IN, AttendanceStatus.REJECTED]),
        )),
        "task_count": db.scalar(select(func.count()).select_from(TaskAssignment).where(
            TaskAssignment.assignee_id == user_id,
            TaskAssignment.status == TaskAssignmentStatus.VERIFIED,
        )),
    }


def qualifies(requirements, metrics: dict[str, int]) -> bool:
    operators = {
        ">=": lambda actual, threshold: actual >= threshold,
        "<=": lambda actual, threshold: actual <= threshold,
        "=": lambda actual, threshold: actual == threshold,
    }
    return all(req.operator in operators and operators[req.operator](metrics.get(req.metric, 0), req.threshold)
               for req in requirements)


def qualified_milestones(db: Session, user_id, community_id) -> list[Milestone]:
    metrics = user_metrics(db, user_id, community_id)
    result = []
    for milestone in db.scalars(select(Milestone).where(
        Milestone.community_id == community_id, Milestone.is_active.is_(True)
    )):
        requirements = list(db.scalars(select(MilestoneRequirement).where(
            MilestoneRequirement.milestone_id == milestone.id
        )))
        if qualifies(requirements, metrics):
            result.append(milestone)
    return result


def current_rank(db: Session, user_id, community_id) -> Rank | None:
    points = user_metrics(db, user_id, community_id)["impact_points"]
    return db.scalar(select(Rank).where(
        Rank.community_id == community_id, Rank.is_active.is_(True), Rank.minimum_points <= points
    ).order_by(Rank.minimum_points.desc()))


def award_badge(db: Session, badge: Badge, user_id, idempotency_key: str) -> BadgeAward:
    existing = db.scalar(select(BadgeAward).where(BadgeAward.idempotency_key == idempotency_key))
    if existing:
        return existing
    from datetime import UTC, datetime
    award = BadgeAward(badge_id=badge.id, user_id=user_id, idempotency_key=idempotency_key,
                       awarded_at=datetime.now(UTC))
    db.add(award); db.commit(); return award
