"""Seed behavior tests."""

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import (
    AchievementRule,
    Badge,
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


def test_default_badge_seed_is_configurable_and_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'badge-seed.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _user, community, _event = create_event_context(session)

        seed_community_recognition(session, community.id)
        seed_community_recognition(session, community.id)

        badges = {
            badge.slug: badge.requirements
            for badge in session.scalars(
                select(Badge).where(Badge.community_id == community.id)
            )
        }
        assert badges == {
            "first-step": {"operator": ">=", "metric": "attendance_count", "value": 1},
            "regular": {"operator": ">=", "metric": "attendance_count", "value": 5},
            "consistent": {"operator": ">=", "metric": "attendance_count", "value": 10},
            "task-starter": {"operator": ">=", "metric": "task_count", "value": 1},
            "doer": {"operator": ">=", "metric": "task_count", "value": 10},
            "community-helper": {
                "operator": ">=",
                "metric": "service_activities",
                "value": 5,
            },
            "facilitator": {
                "operator": ">=",
                "metric": "organized_event_count",
                "value": 1,
            },
            "community-builder": {
                "operator": ">=",
                "metric": "community_builder_milestones",
                "value": 1,
            },
        }
    engine.dispose()


def test_community_champion_rule_seed_is_configurable_and_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'achievement-seed.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _user, community, _event = create_event_context(session)

        seed_community_recognition(session, community.id)
        seed_community_recognition(session, community.id)

        rule = session.scalar(
            select(AchievementRule).where(
                AchievementRule.community_id == community.id,
                AchievementRule.slug == "community-champion",
            )
        )
        assert rule.condition_tree == {
            "operator": "AND",
            "conditions": [
                {"operator": ">=", "metric": "attendance_count", "value": 20},
                {"operator": ">=", "metric": "task_count", "value": 10},
                {"operator": ">=", "metric": "peer_confirmations", "value": 10},
                {"operator": ">=", "metric": "leadership_activities", "value": 3},
                {"operator": ">=", "metric": "impact_points", "value": 500},
            ],
        }
        assert rule.reward_definition == {
            "badge": "community-champion",
            "impact_points": 50,
        }
        assert session.scalar(
            select(func.count()).select_from(AchievementRule).where(
                AchievementRule.slug == "community-champion"
            )
        ) == 1
    engine.dispose()


def test_optional_streak_rules_are_seeded_disabled_and_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'streak-seed.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _user, community, _event = create_event_context(session)

        seed_community_recognition(session, community.id)
        seed_community_recognition(session, community.id)

        rules = {
            rule.slug: (rule.condition_tree, rule.is_active)
            for rule in session.scalars(
                select(AchievementRule).where(
                    AchievementRule.community_id == community.id,
                    AchievementRule.slug.like("%-streak"),
                )
            )
        }
        assert rules == {
            "three-event-attendance-streak": (
                {"operator": ">=", "metric": "attendance_count", "value": 3},
                False,
            ),
            "five-task-completion-streak": (
                {"operator": ">=", "metric": "task_count", "value": 5},
                False,
            ),
            "four-week-activity-streak": (
                {"operator": ">=", "metric": "consecutive_activities", "value": 4},
                False,
            ),
        }
    engine.dispose()
