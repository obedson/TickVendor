"""Recognition qualification and idempotent automatic award engine."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models import (
    AchievementAward,
    AchievementRule,
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
    RankProgression,
    RankRequirement,
    Task,
    TaskAssignment,
    TaskAssignmentStatus,
)
from src.services.achievement import evaluate_condition
from src.services.impact import award_points
from src.services.notification import audit, notify


def longest_consecutive_days(values) -> int:
    days = sorted({value.date() for value in values})
    longest = current = 0
    previous = None
    for day in days:
        current = current + 1 if previous and (day - previous).days == 1 else 1
        longest = max(longest, current)
        previous = day
    return longest


def user_metrics(db: Session, user_id, community_id) -> dict[str, int]:
    attendance_count = db.scalar(select(func.count()).select_from(Attendance).where(
        Attendance.user_id == user_id,
        Attendance.event_id.in_(select(Event.id).where(Event.community_id == community_id)),
        Attendance.status.notin_([AttendanceStatus.NOT_CHECKED_IN, AttendanceStatus.REJECTED]),
    ))
    activity_dates = db.scalars(select(Activity.occurred_at).where(
        Activity.user_id == user_id,
        Activity.community_id == community_id,
        Activity.status == ActivityStatus.VERIFIED,
    )).all()
    return {
        "impact_points": db.scalar(select(func.coalesce(func.sum(ImpactTransaction.points), 0)).where(
            ImpactTransaction.user_id == user_id, ImpactTransaction.community_id == community_id,
            ImpactTransaction.status == ImpactTransactionStatus.POSTED,
        )),
        "attendance_count": attendance_count,
        "event_participation": attendance_count,
        "consecutive_activities": longest_consecutive_days(activity_dates),
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


def _rank_qualifies(db: Session, rank: Rank, user_id, metrics: dict[str, int]) -> bool:
    if rank.minimum_points > metrics["impact_points"]:
        return False
    for requirement in db.scalars(select(RankRequirement).where(RankRequirement.rank_id == rank.id)):
        if requirement.requirement_type == "milestone":
            actual = db.scalar(select(func.count()).select_from(MilestoneAward).where(
                MilestoneAward.user_id == user_id, MilestoneAward.milestone_id == requirement.reference_id,
            ))
        elif requirement.requirement_type == "badge":
            actual = db.scalar(select(func.count()).select_from(BadgeAward).where(
                BadgeAward.user_id == user_id, BadgeAward.badge_id == requirement.reference_id,
                BadgeAward.revoked_at.is_(None),
            ))
        else:
            actual = metrics.get(requirement.requirement_type, 0)
        if actual < requirement.threshold:
            return False
    return True


def current_rank(db: Session, user_id, community_id) -> Rank | None:
    metrics = user_metrics(db, user_id, community_id)
    for rank in db.scalars(select(Rank).where(
        Rank.community_id == community_id, Rank.is_active.is_(True),
    ).order_by(Rank.sort_order.desc(), Rank.minimum_points.desc())):
        if _rank_qualifies(db, rank, user_id, metrics):
            return rank
    return None


def next_rank(db: Session, user_id, community_id) -> Rank | None:
    metrics = user_metrics(db, user_id, community_id)
    current = current_rank(db, user_id, community_id)
    ranks = db.scalars(select(Rank).where(
        Rank.community_id == community_id, Rank.is_active.is_(True),
    ).order_by(Rank.sort_order.asc(), Rank.minimum_points.asc()))
    for rank in ranks:
        if (current is None or rank.sort_order > current.sort_order) and not _rank_qualifies(db, rank, user_id, metrics):
            return rank
    return None


def evaluate_rank_progression(db: Session, user_id, community_id) -> Rank | None:
    rank = current_rank(db, user_id, community_id)
    if rank is None:
        return None
    existing = db.scalar(select(RankProgression.id).where(
        RankProgression.rank_id == rank.id, RankProgression.user_id == user_id,
    ))
    if existing:
        return rank
    highest = db.scalar(select(func.max(Rank.sort_order)).join(
        RankProgression, RankProgression.rank_id == Rank.id,
    ).where(RankProgression.user_id == user_id, RankProgression.community_id == community_id))
    if highest is not None and highest >= rank.sort_order:
        return rank
    progression = RankProgression(rank_id=rank.id, user_id=user_id, community_id=community_id,
                                  achieved_at=datetime.now(UTC))
    db.add(progression); db.flush()
    audit(db, actor_id=None, community_id=community_id, action="rank.achieved",
          target_type="rank_progression", target_id=progression.id,
          metadata={"rank_id": str(rank.id), "user_id": str(user_id)}, commit=False)
    notify(db, user_id, "rank_achieved", "New rank achieved", f"You reached {rank.name}.",
           {"rank_id": str(rank.id)}, deduplication_key=f"rank:{rank.id}:user:{user_id}", commit=False)
    db.commit()
    return rank


def award_badge(db: Session, badge: Badge, user_id, idempotency_key: str, *, commit: bool = True) -> BadgeAward:
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
    if commit:
        db.commit()
    audit(db, actor_id=None, community_id=badge.community_id, action="badge.awarded",
          target_type="badge_award", target_id=award.id,
          metadata={"badge_id": str(badge.id), "user_id": str(user_id)}, commit=commit)
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


def evaluate_achievement_rules(db: Session, user_id, community_id, metrics: dict) -> int:
    awarded = 0
    for rule in db.scalars(select(AchievementRule).where(
        AchievementRule.community_id == community_id, AchievementRule.is_active.is_(True),
    )):
        if not evaluate_condition(rule.condition_tree, metrics):
            continue
        existing = db.scalar(select(AchievementAward.id).where(
            AchievementAward.rule_id == rule.id, AchievementAward.user_id == user_id,
        ))
        if existing:
            continue
        definition = rule.reward_definition
        if not isinstance(definition, dict):
            raise TypeError("Achievement reward definition must be an object")
        award = AchievementAward(rule_id=rule.id, user_id=user_id, community_id=community_id,
                                 awarded_at=datetime.now(UTC))
        db.add(award); db.flush()
        if definition.get("impact_points"):
            award_points(db, user_id=user_id, community_id=community_id, source_type="achievement_reward",
                         source_id=rule.id, idempotency_key=f"achievement:{rule.id}:user:{user_id}:points",
                         reason=f"Achievement reward: {rule.name}", points_override=int(definition["impact_points"]),
                         commit=False)
        if definition.get("badge"):
            badge = db.scalar(select(Badge).where(Badge.community_id == community_id,
                                                  Badge.slug == definition["badge"], Badge.is_active.is_(True)))
            if badge is None:
                raise ValueError("Achievement reward badge not found")
            award_badge(db, badge, user_id, f"achievement:{rule.id}:user:{user_id}:badge", commit=False)
        audit(db, actor_id=None, community_id=community_id, action="achievement.rewarded",
              target_type="achievement_award", target_id=award.id,
              metadata={"rule_id": str(rule.id), "user_id": str(user_id)}, commit=False)
        notify(db, user_id, "achievement_awarded", "Achievement earned", f"You earned {rule.name}.",
               {"rule_id": str(rule.id)}, deduplication_key=f"achievement:{rule.id}:user:{user_id}", commit=False)
        awarded += 1
    db.commit()
    return awarded


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

    achievement_rules_awarded = evaluate_achievement_rules(db, user_id, community_id, user_metrics(db, user_id, community_id))
    evaluate_rank_progression(db, user_id, community_id)
    return {
        "milestones_awarded": milestones_awarded,
        "badges_awarded": badges_awarded,
        "achievement_rules_awarded": achievement_rules_awarded,
    }
