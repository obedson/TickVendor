"""Effective community rules and separately governed platform ceilings."""
from fastapi import HTTPException
from sqlalchemy import case, select

from src.models import PointCeiling, PointRule


def applicable_rule(db, community_id, source_type):
    # Explicit CASE avoids PostgreSQL DESC NULLS FIRST choosing platform defaults.
    return db.scalar(select(PointRule).where(
        PointRule.source_type == source_type, PointRule.is_active.is_(True),
        (PointRule.community_id == community_id) | PointRule.community_id.is_(None),
    ).order_by(case((PointRule.community_id == community_id, 0), else_=1),
               PointRule.updated_at.desc(), PointRule.id))


def ceiling(db, source_type):
    # PostgreSQL shares this lock across readers; cap changes wait for in-flight awards.
    return db.scalar(select(PointCeiling.maximum_points).where(
        PointCeiling.source_type == source_type).with_for_update(read=True))


def task_policy(db, community_id):
    rule = applicable_rule(db, community_id, "task_completion")
    maximum = ceiling(db, "task_completion")
    amount = max(0, rule.points) if rule else 0
    if maximum is not None:
        amount = min(amount, maximum)
    return {"community_points": amount, "platform_maximum": maximum,
            "configured": rule is not None,
            "warning": None if rule else "No active Task Completion rule. Only zero-point tasks can be created."}


def effective_task_points(db, task, policy=None):
    policy = policy if policy is not None else task_policy(db, task.community_id)
    if not task.impact_point_reward:
        return 0
    if task.reward_mode == "legacy_rule":
        return policy["community_points"]
    return min(task.impact_point_reward, policy["community_points"])


def validate_task_reward(db, community_id, points):
    policy = task_policy(db, community_id)
    if points > 0 and policy["platform_maximum"] is None:
        raise HTTPException(422, "Platform Task Completion maximum is not configured; ask a Super Admin first or use zero points")
    if points > policy["community_points"]:
        raise HTTPException(422, "Task reward exceeds the effective community Task Completion award; configure the rule first or use zero points")

def task_award_points(db, task):
    policy = task_policy(db, task.community_id)
    if not policy["configured"]:
        # Preserve the deployed positive-reward verification precondition.
        raise HTTPException(409, "No active point rule configured")
    return effective_task_points(db, task, policy)
