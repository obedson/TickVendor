"""Idempotent development seed data for configurable business rules."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models import ContributionBand, EventCategory, PointRule

EVENT_CATEGORIES = (
    "technology",
    "education",
    "business",
    "community",
    "agriculture",
    "entertainment",
    "sports",
    "training",
    "conference",
    "workshop",
    "networking",
    "volunteer",
    "fundraising",
)
POINT_RULES = {
    "attendance": 10,
    "task_completion": 20,
    "volunteer_activity": 15,
    "peer_verification": 2,
    "leadership_activity": 30,
}
CONTRIBUTION_BANDS = (
    (Decimal(1), Decimal("999.99"), 2),
    (Decimal(1000), Decimal("4999.99"), 5),
    (Decimal(5000), Decimal("9999.99"), 10),
    (Decimal(10000), None, 15),
)


def seed_business_configuration(db: Session) -> None:
    existing_categories = set(db.scalars(select(EventCategory.slug)))
    db.add_all(
        EventCategory(slug=slug, name=slug.replace("_", " ").title())
        for slug in EVENT_CATEGORIES
        if slug not in existing_categories
    )

    existing_rules = set(
        db.scalars(select(PointRule.source_type).where(PointRule.community_id.is_(None)))
    )
    db.add_all(
        PointRule(source_type=source_type, points=points)
        for source_type, points in POINT_RULES.items()
        if source_type not in existing_rules
    )

    existing_minimums = set(
        db.scalars(
            select(ContributionBand.minimum_amount).where(
                ContributionBand.community_id.is_(None), ContributionBand.currency == "NGN"
            )
        )
    )
    db.add_all(
        ContributionBand(
            currency="NGN",
            minimum_amount=minimum,
            maximum_amount=maximum,
            points=points,
        )
        for minimum, maximum, points in CONTRIBUTION_BANDS
        if minimum not in existing_minimums
    )
    db.commit()
