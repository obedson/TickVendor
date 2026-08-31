"""Contribution verification and configurable reward service."""

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.authorization import require_community_role
from src.models import (
    ActivityStatus,
    Contribution,
    ContributionBand,
    ImpactTransaction,
    ImpactTransactionStatus,
    MembershipRole,
    User,
)
from src.services.impact import award_points


def record_contribution(db: Session, contributor: User, **values) -> Contribution:
    contribution = Contribution(contributor_id=contributor.id, status=ActivityStatus.PENDING, **values)
    db.add(contribution); db.commit(); return contribution


def verify_contribution(db: Session, contribution: Contribution, verifier: User, approve: bool):
    require_community_role(db, contribution.community_id, verifier, MembershipRole.ORGANIZER)
    if contribution.status != ActivityStatus.PENDING:
        raise HTTPException(status_code=409, detail="Contribution already reviewed")
    contribution.status = ActivityStatus.VERIFIED if approve else ActivityStatus.REJECTED
    contribution.verified_by_id = verifier.id
    db.commit()
    if approve and contribution.amount is not None:
        band = db.scalar(select(ContributionBand).where(
            ContributionBand.currency == contribution.currency,
            ContributionBand.is_active.is_(True),
            ContributionBand.minimum_amount <= contribution.amount,
            (ContributionBand.maximum_amount.is_(None)) | (ContributionBand.maximum_amount >= contribution.amount),
            (ContributionBand.community_id == contribution.community_id) | ContributionBand.community_id.is_(None),
        ).order_by(ContributionBand.community_id.desc(), ContributionBand.minimum_amount.desc()))
        if band:
            points = band.points
            if band.per_user_period_cap is not None:
                awarded = db.scalar(select(func.coalesce(func.sum(ImpactTransaction.points), 0)).where(
                    ImpactTransaction.user_id == contribution.contributor_id,
                    ImpactTransaction.community_id == contribution.community_id,
                    ImpactTransaction.source_type == "contribution",
                    ImpactTransaction.status == ImpactTransactionStatus.POSTED,
                ))
                points = max(0, min(points, band.per_user_period_cap - awarded))
            if points == 0:
                return contribution
            # Contribution rules are represented through the central point-rule source.
            award_points(
                db, user_id=contribution.contributor_id, community_id=contribution.community_id,
                source_type="contribution", source_id=contribution.id,
                idempotency_key=f"contribution:{contribution.id}:verified",
                reason=f"Verified contribution on {datetime.now(UTC).date()}",
                points_override=points,
            )
    return contribution
