"""Idempotent Impact Point award service."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models import ImpactTransaction, ImpactTransactionStatus, PointRule


def award_points(
    db: Session, *, user_id, community_id, source_type: str, source_id,
    idempotency_key: str, reason: str, event_id=None, task_id=None,
) -> ImpactTransaction:
    existing = db.scalar(select(ImpactTransaction).where(
        ImpactTransaction.idempotency_key == idempotency_key
    ))
    if existing:
        return existing
    rule = db.scalar(select(PointRule).where(
        PointRule.source_type == source_type, PointRule.is_active.is_(True),
        (PointRule.community_id == community_id) | PointRule.community_id.is_(None),
    ).order_by(PointRule.community_id.desc()))
    if rule is None:
        raise HTTPException(status_code=409, detail="No active point rule configured")
    transaction = ImpactTransaction(
        idempotency_key=idempotency_key, user_id=user_id, community_id=community_id,
        points=rule.points, source_type=source_type, source_id=source_id,
        event_id=event_id, task_id=task_id, reason=reason,
        status=ImpactTransactionStatus.POSTED,
    )
    db.add(transaction)
    db.commit()
    return transaction
