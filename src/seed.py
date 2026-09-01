"""Idempotent development seed data for configurable business rules."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models import (
    ContributionBand,
    EventCategory,
    Milestone,
    MilestoneRequirement,
    PointRule,
    Rank,
)

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
COMMUNITY_BUILDER_REQUIREMENTS = {
    "impact_points": 300,
    "attendance_count": 10,
    "task_count": 5,
    "contribution_count": 1,
}
DEFAULT_RANKS = (
    ("Starter", "starter", 0),
    ("Active Member", "active-member", 50),
    ("Contributor", "contributor", 150),
    ("Community Builder", "community-builder", 300),
    ("Community Leader", "community-leader", 500),
    ("Impact Champion", "impact-champion", 800),
)


def seed_community_recognition(db: Session, community_id) -> None:
    milestone = db.scalar(
        select(Milestone).where(
            Milestone.community_id == community_id,
            Milestone.slug == "community-builder",
        )
    )
    if milestone is None:
        milestone = Milestone(
            community_id=community_id,
            name="Community Builder",
            slug="community-builder",
            description="Sustained attendance, execution, and contribution.",
        )
        db.add(milestone)
        db.flush()
    existing = set(
        db.scalars(
            select(MilestoneRequirement.metric).where(
                MilestoneRequirement.milestone_id == milestone.id
            )
        )
    )
    db.add_all(
        MilestoneRequirement(
            milestone_id=milestone.id,
            metric=metric,
            operator=">=",
            threshold=threshold,
        )
        for metric, threshold in COMMUNITY_BUILDER_REQUIREMENTS.items()
        if metric not in existing
    )
    existing_ranks = set(
        db.scalars(select(Rank.slug).where(Rank.community_id == community_id))
    )
    db.add_all(
        Rank(
            community_id=community_id,
            name=name,
            slug=slug,
            minimum_points=minimum_points,
            sort_order=sort_order,
        )
        for sort_order, (name, slug, minimum_points) in enumerate(DEFAULT_RANKS, start=1)
        if slug not in existing_ranks
    )
    db.commit()


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
