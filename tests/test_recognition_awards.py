"""Automatic recognition award tests."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import (
    AchievementAward,
    AuditLog,
    Badge,
    BadgeAward,
    ImpactTransaction,
    ImpactTransactionStatus,
    Milestone,
    MilestoneAward,
    MilestoneRequirement,
    Notification,
)
from src.services.recognition import evaluate_recognition
from tests.test_database import create_event_context


def test_recognition_evaluation_awards_milestone_badge_and_reward_once(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'auto-recognition.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        user, community, _event = create_event_context(db)
        milestone = Milestone(
            community_id=community.id,
            name="Builder",
            slug="builder",
            reward_points=25,
        )
        badge = Badge(
            community_id=community.id,
            name="Century",
            slug="century",
            category="impact",
            requirements={"operator": ">=", "metric": "impact_points", "value": 100},
            reward_points=10,
        )
        db.add_all([milestone, badge])
        db.flush()
        db.add_all(
            [
                MilestoneRequirement(
                    milestone_id=milestone.id,
                    metric="impact_points",
                    operator=">=",
                    threshold=100,
                ),
                ImpactTransaction(
                    idempotency_key="recognition-base-points",
                    user_id=user.id,
                    community_id=community.id,
                    points=100,
                    source_type="test",
                    reason="Test points",
                    status=ImpactTransactionStatus.POSTED,
                ),
            ]
        )
        db.commit()

        first = evaluate_recognition(db, user.id, community.id)
        second = evaluate_recognition(db, user.id, community.id)

        assert first["milestones_awarded"] == 1
        assert first["badges_awarded"] == 1
        assert second["milestones_awarded"] == 0
        assert second["badges_awarded"] == 0
        assert db.query(MilestoneAward).count() == 1
        assert db.query(BadgeAward).count() == 1
        reward_points = sum(
            row.points
            for row in db.query(ImpactTransaction).filter(
                ImpactTransaction.source_type.in_(["milestone_reward", "badge_reward"])
            )
        )
        assert reward_points == 35
        assert db.query(AchievementAward).count() == 0
    engine.dispose()


def test_recognition_executes_configured_achievement_rewards_once(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'achievement-reward-flow.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        user, community, _event = create_event_context(db)
        badge = Badge(community_id=community.id, name="Champion", slug="champion-flow",
                      category="impact", requirements={}, reward_points=0)
        rule = __import__("src.models", fromlist=["AchievementRule"]).AchievementRule(
            community_id=community.id, name="Flow Champion", slug="flow-champion",
            condition_tree={"operator": ">=", "metric": "impact_points", "value": 10},
            reward_definition={"impact_points": 15, "badge": "champion-flow"},
        )
        db.add_all([badge, rule, ImpactTransaction(
            idempotency_key="flow-base", user_id=user.id, community_id=community.id,
            points=10, source_type="test", reason="flow", status=ImpactTransactionStatus.POSTED)])
        db.commit()
        first = evaluate_recognition(db, user.id, community.id)
        second = evaluate_recognition(db, user.id, community.id)
        assert first["achievement_rules_awarded"] == 1
        assert second["achievement_rules_awarded"] == 0
        assert db.query(AchievementAward).count() == 1
        assert db.query(BadgeAward).count() == 1
        assert db.query(ImpactTransaction).filter_by(source_type="achievement_reward").count() == 1
        assert db.query(AuditLog).filter_by(action="achievement.rewarded").count() == 1
        assert db.query(Notification).filter_by(notification_type="achievement_awarded").count() == 1
    engine.dispose()
