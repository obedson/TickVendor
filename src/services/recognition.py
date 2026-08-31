"""Recognition qualification and idempotent automatic award engine."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models import (
    Activity,
    ActivityStatus,
    Attendance,
    AttendanceStatus,
    Badge,
    BadgeAward,
    Contribution,
    EngagementDimension,
    Event,
    ImpactTransaction,
    ImpactTransactionStatus,
    Milestone,
    MilestoneAward,
    MilestoneRequirement,
    PeerConfirmation,
    PeerConfirmationDecision,
    Rank,
    Task,
    TaskAssignment,
    TaskAssignmentStatus,
)
from src.services.achievement import evaluate_condition
from src.services.impact import award_points
from src.services.notification import notify


def user_metrics(db: Session, user_id, community_id) -> dict[str, int]:
    return {
        "impact_points": db.scalar(select(func.coalesce(func.sum(ImpactTransaction.points), 0)).where(
            ImpactTransaction.user_id == user_id, ImpactTransaction.community_id == community_id,
            ImpactTransaction.status == ImpactTransactionStatus.POSTED,
        )),
        "attendance_count": db.scalar(select(func.count()).select_from(Attendance).where(
            Attendance.user_id == user_id,
            Attendance.event_id.in_(select(Event.id).where(Event.community_id == community_id)),
            Attendance.status.notin_([AttendanceStatus.NOT_CHECKED_IN, AttendanceStatus.REJECTED]),
        )),
        "task_count": db.scalar(select(func.count()).select_from(TaskAssignment).where(
            TaskAssignment.assignee_id == user_id,
            TaskAssignment.task_id.in_(select(Task.id).where(Task.community_id == community_id)),
            TaskAssignment.status == TaskAssignmentStatus.VERIFIED,
        )),
        "contribution_count": db.scalar(select(func.count()).select_from(Contribution).where(
            Contribution.contributor_id == user_id,
            Contribution.community_id == community_id,
            Contribution.status == ActivityStatus.VERIFIED,
        )),
        "service_activities": db.scalar(select(func.count()).select_from(Activity).where(
            Activity.user_id == user_id,
            Activity.community_id == community_id,
            Activity.dimension == EngagementDimension.SERVICE,
            Activity.status == ActivityStatus.VERIFIED,
        )),
        "leadership_activities": db.scalar(select(func.count()).select_from(Activity).where(
            Activity.user_id == user_id,
            Activity.community_id == community_id,
            Activity.dimension == EngagementDimension.LEADERSHIP,
            Activity.status == ActivityStatus.VERIFIED,
        )),
        "peer_confirmations": db.scalar(select(func.count()).select_from(PeerConfirmation).where(
            PeerConfirmation.subject_id == user_id,
            PeerConfirmation.event_id.in_(select(Event.id).where(Event.community_id == community_id)),
            PeerConfirmation.decision == PeerConfirmationDecision.CONFIRMED,
        )),
    }


def qualifies(requirements, metrics: dict[str, int]) -> bool:
    operators = {
        ">=": lambda actual, threshold: actual >= threshold,
        "<=": lambda actual, threshold: actual <= threshold,
        "=": lambda actual, threshold: actual == threshold,
    }
    return all(
        req.operator in operators
        and operators[req.operator](metrics.get(req.metric, 0), req.threshold)
        for req in requirements
    )


def qualified_milestones(db: Session, user_id, community_id) -> list[Milestone]:
    metrics = user_metrics(db, user_id, community_id)
    result = []
    for milestone in db.scalars(select(Milestone).where(
        Milestone.community_id == community_id, Milestone.is_active.is_(True)
    )):
        requirements = list(db.scalars(select(MilestoneRequirement).where(
            MilestoneRequirement.milestone_id == milestone.id
        )))
        if requirements and qualifies(requirements, metrics):
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
    award = BadgeAward(
        badge_id=badge.id,
        user_id=user_id,
        idempotency_key=idempotency_key,
        awarded_at=datetime.now(UTC),
    )
    db.add(award)
    db.commit()
    return award


def award_milestone(db: Session, milestone: Milestone, user_id) -> MilestoneAward:
    idempotency_key = f"milestone:{milestone.id}:user:{user_id}"
    existing = db.scalar(select(MilestoneAward).where(
        MilestoneAward.idempotency_key == idempotency_key
    ))
    if existing:
        return existing
    award = MilestoneAward(
        milestone_id=milestone.id,
        user_id=user_id,
        idempotency_key=idempotency_key,
        awarded_at=datetime.now(UTC),
    )
    db.add(award)
    db.commit()
    return award


def evaluate_recognition(db: Session, user_id, community_id) -> dict[str, int]:
    """Evaluate configured milestones and badges without duplicate awards."""
    milestones_awarded = 0
    badges_awarded = 0

    for milestone in qualified_milestones(db, user_id, community_id):
        already_awarded = db.scalar(select(MilestoneAward.id).where(
            MilestoneAward.milestone_id == milestone.id,
            MilestoneAward.user_id == user_id,
        ))
        if already_awarded:
            continue
        award_milestone(db, milestone, user_id)
        milestones_awarded += 1
        if milestone.reward_points:
            award_points(
                db,
                user_id=user_id,
                community_id=community_id,
                source_type="milestone_reward",
                source_id=milestone.id,
                idempotency_key=f"milestone-reward:{milestone.id}:user:{user_id}",
                reason=f"Milestone achieved: {milestone.name}",
                points_override=milestone.reward_points,
            )
        notify(
            db,
            user_id,
            "milestone_awarded",
            "Milestone reached",
            f"Congratulations! You reached {milestone.name}.",
            {"milestone_id": str(milestone.id)},
        )

    metrics = user_metrics(db, user_id, community_id)
    for badge in db.scalars(select(Badge).where(
        Badge.community_id == community_id,
        Badge.is_active.is_(True),
    )):
        already_awarded = db.scalar(select(BadgeAward.id).where(
            BadgeAward.badge_id == badge.id,
            BadgeAward.user_id == user_id,
        ))
        if already_awarded or not badge.requirements:
            continue
        if not evaluate_condition(badge.requirements, metrics):
            continue
        award_badge(db, badge, user_id, f"badge:{badge.id}:user:{user_id}")
        badges_awarded += 1
        if badge.reward_points:
            award_points(
                db,
                user_id=user_id,
                community_id=community_id,
                source_type="badge_reward",
                source_id=badge.id,
                idempotency_key=f"badge-reward:{badge.id}:user:{user_id}",
                reason=f"Badge earned: {badge.name}",
                points_override=badge.reward_points,
            )
        notify(
            db,
            user_id,
            "badge_awarded",
            "New badge earned",
            f"You earned the {badge.name} badge.",
            {"badge_id": str(badge.id)},
        )

    return {
        "milestones_awarded": milestones_awarded,
        "badges_awarded": badges_awarded,
    }
