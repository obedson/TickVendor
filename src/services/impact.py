"""Idempotent Impact Point award service."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models import ImpactTransaction, ImpactTransactionStatus
from src.services.point_policy import applicable_rule, ceiling


def award_points(
    db: Session, *, user_id, community_id, source_type: str, source_id,
    idempotency_key: str, reason: str, event_id=None, task_id=None, points_override: int | None = None,
    commit: bool = True,
) -> ImpactTransaction:
    existing = db.scalar(select(ImpactTransaction).where(
        ImpactTransaction.idempotency_key == idempotency_key
    ))
    if existing:
        return existing
    rule = applicable_rule(db, community_id, source_type)
    if rule is None and points_override is None:
        raise HTTPException(status_code=409, detail="No active point rule configured")
    amount = points_override if points_override is not None else rule.points
    maximum = ceiling(db, source_type)
    if maximum is not None:
        amount = min(amount, maximum)
    transaction = ImpactTransaction(
        idempotency_key=idempotency_key, user_id=user_id, community_id=community_id,
        points=amount,
        source_type=source_type, source_id=source_id,
        event_id=event_id, task_id=task_id, reason=reason,
        status=ImpactTransactionStatus.POSTED,
    )
    try:
        # A savepoint preserves the caller transaction after an idempotency race.
        with db.begin_nested():
            db.add(transaction)
            db.flush()
        if commit:
            db.commit()
    except IntegrityError:
        existing = db.scalar(select(ImpactTransaction).where(
            ImpactTransaction.idempotency_key == idempotency_key,
        ))
        if existing is not None:
            return existing
        raise
    return transaction
