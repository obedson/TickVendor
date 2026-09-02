"""Leaderboard query service."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.authorization import require_community_role
from src.models import (
    Activity,
    ActivityStatus,
    Attendance,
    AttendanceStatus,
    EngagementDimension,
    Event,
    ImpactTransaction,
    ImpactTransactionStatus,
    Leaderboard,
    MembershipRole,
    Profile,
    Task,
    TaskAssignment,
    TaskAssignmentStatus,
    User,
)


def leaderboard_entries(db: Session, leaderboard: Leaderboard, viewer: User, limit: int = 100):
    require_community_role(db, leaderboard.community_id, viewer, MembershipRole.MEMBER)
    if not leaderboard.is_enabled:
        return []
    metric = leaderboard.metric
    if metric == "overall":
        score_expression = func.sum(ImpactTransaction.points)
        score_query = select(ImpactTransaction.user_id, score_expression.label("score")).where(
            ImpactTransaction.community_id == leaderboard.community_id,
            ImpactTransaction.status == ImpactTransactionStatus.POSTED,
        ).group_by(ImpactTransaction.user_id)
    elif metric in {"attendance", "event"}:
        score_query = select(Attendance.user_id, func.count().label("score")).where(
            Attendance.event_id.in_(select(Event.id).where(Event.community_id == leaderboard.community_id)),
            Attendance.status.notin_([AttendanceStatus.NOT_CHECKED_IN, AttendanceStatus.REJECTED]),
        ).group_by(Attendance.user_id)
    elif metric == "tasks":
        score_query = select(TaskAssignment.assignee_id.label("user_id"), func.count().label("score")).where(
            TaskAssignment.task_id.in_(select(Task.id).where(Task.community_id == leaderboard.community_id)),
            TaskAssignment.status == TaskAssignmentStatus.VERIFIED,
        ).group_by(TaskAssignment.assignee_id)
    elif metric in {"service", "leadership"}:
        dimension = EngagementDimension.SERVICE if metric == "service" else EngagementDimension.LEADERSHIP
        score_query = select(Activity.user_id, func.count().label("score")).where(
            Activity.community_id == leaderboard.community_id, Activity.dimension == dimension,
            Activity.status == ActivityStatus.VERIFIED,
        ).group_by(Activity.user_id)
    else:
        return []
    scores = score_query.subquery()
    rows = db.execute(
        select(
            scores.c.user_id,
            Profile.username,
            scores.c.score,
        )
        .select_from(scores)
        .join(Profile, Profile.user_id == scores.c.user_id)
        .where(Profile.visibility != "private")
        .order_by(scores.c.score.desc(), scores.c.user_id)
        .limit(min(limit, leaderboard.max_entries))
    )
    return [
        {"user_id": str(user_id), "username": username, "score": score}
        for user_id, username, score in rows
    ]
