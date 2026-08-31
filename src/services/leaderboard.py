"""Leaderboard query service."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.authorization import require_community_role
from src.models import (
    ImpactTransaction,
    ImpactTransactionStatus,
    Leaderboard,
    MembershipRole,
    Profile,
    User,
)


def leaderboard_entries(db: Session, leaderboard: Leaderboard, viewer: User, limit: int = 100):
    require_community_role(db, leaderboard.community_id, viewer, MembershipRole.MEMBER)
    if not leaderboard.is_enabled:
        return []
    if leaderboard.metric != "overall":
        return []
    rows = db.execute(
        select(
            ImpactTransaction.user_id,
            Profile.username,
            func.sum(ImpactTransaction.points).label("score"),
        )
        .join(Profile, Profile.user_id == ImpactTransaction.user_id)
        .where(
            ImpactTransaction.community_id == leaderboard.community_id,
            ImpactTransaction.status == ImpactTransactionStatus.POSTED,
        )
        .group_by(ImpactTransaction.user_id, Profile.username)
        .order_by(func.sum(ImpactTransaction.points).desc())
        .limit(min(limit, leaderboard.max_entries))
    )
    return [
        {"user_id": str(user_id), "username": username, "score": score}
        for user_id, username, score in rows
    ]
