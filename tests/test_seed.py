"""Seed behavior tests."""

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import (
    ContributionBand,
    EventCategory,
    Milestone,
    MilestoneRequirement,
    PointRule,
    Rank,
)
from src.seed import seed_business_configuration, seed_community_recognition
from tests.test_database import create_event_context


def test_business_configuration_seed_is_database_backed_and_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'seed.db'}")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        seed_business_configuration(session)
        seed_business_configuration(session)
        assert session.scalar(select(func.count()).select_from(EventCategory)) == 13
        assert session.scalar(select(func.count()).select_from(PointRule)) == 5
        assert session.scalar(select(func.count()).select_from(ContributionBand)) == 4

    engine.dispose()


def test_community_builder_milestone_seed_is_configurable_and_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'recognition-seed.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _user, community, _event = create_event_context(session)

        seed_community_recognition(session, community.id)
        seed_community_recognition(session, community.id)

        milestone = session.scalar(
            select(Milestone).where(
                Milestone.community_id == community.id,
                Milestone.slug == "community-builder",
            )
        )
        requirements = {
            item.metric: item.threshold
            for item in session.scalars(
                select(MilestoneRequirement).where(
                    MilestoneRequirement.milestone_id == milestone.id
                )
            )
        }
        assert requirements == {
            "impact_points": 300,
            "attendance_count": 10,
            "task_count": 5,
            "contribution_count": 1,
        }
        assert session.scalar(select(func.count()).select_from(Milestone)) == 1
    engine.dispose()


def test_default_rank_seed_is_configurable_and_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'rank-seed.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _user, community, _event = create_event_context(session)

        seed_community_recognition(session, community.id)
        seed_community_recognition(session, community.id)

        ranks = list(
            session.scalars(
                select(Rank)
                .where(Rank.community_id == community.id)
                .order_by(Rank.sort_order)
            )
        )
        assert [(rank.name, rank.minimum_points) for rank in ranks] == [
            ("Starter", 0),
            ("Active Member", 50),
            ("Contributor", 150),
            ("Community Builder", 300),
            ("Community Leader", 500),
            ("Impact Champion", 800),
        ]
    engine.dispose()
