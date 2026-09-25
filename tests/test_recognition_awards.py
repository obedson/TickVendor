"""Automatic recognition award tests."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import (
    AchievementAward,
    AchievementRule,
    AttendanceStatus,
    AuditLog,
    Badge,
    BadgeAward,
    ImpactTransaction,
    ImpactTransactionStatus,
    Milestone,
    MilestoneAward,
    MilestoneRequirement,
    Notification,
    PointRule,
    Venue,
)
from src.schemas.attendance import AttendanceCheckIn
from src.services.attendance import check_in
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


def test_attendance_recognition_flow_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'attendance-recognition.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        user, community, event = create_event_context(db)
        event.geofence_enabled = True; event.geofence_radius_meters = 100
        event.required_verification_methods = ["gps"]
        event.venue = Venue(name="Venue", address="Address", latitude=9, longitude=7)
        badge = Badge(community_id=community.id, name="First attendance", slug="first-attendance-flow",
                      category="participation", requirements={"operator": ">=", "metric": "attendance_count", "value": 1})
        milestone = Milestone(community_id=community.id, name="First event", slug="first-event-recognition", reward_points=5)
        rule = AchievementRule(community_id=community.id, name="Attendance reward", slug="attendance-reward",
                               condition_tree={"operator": ">=", "metric": "attendance_count", "value": 1},
                               reward_definition={"impact_points": 7, "badge": "first-attendance-flow"})
        db.add_all([badge, milestone, rule, PointRule(source_type="attendance", points=10)])
        db.flush(); db.add(MilestoneRequirement(milestone_id=milestone.id, metric="attendance_count", operator=">=", threshold=1)); db.commit()
        attendance = check_in(db, event, user, AttendanceCheckIn(latitude=9, longitude=7, accuracy_meters=12))
        replay = check_in(db, event, user, AttendanceCheckIn(latitude=9, longitude=7, accuracy_meters=12))
        assert attendance.id == replay.id and attendance.status == AttendanceStatus.GPS_VERIFIED
        assert db.query(ImpactTransaction).filter_by(source_type="attendance").count() == 1
        assert db.query(MilestoneAward).filter_by(milestone_id=milestone.id).count() == 1
        assert db.query(BadgeAward).filter_by(badge_id=badge.id).count() == 1
        assert db.query(AchievementAward).filter_by(rule_id=rule.id).count() == 1
        assert db.query(ImpactTransaction).filter_by(source_type="achievement_reward").count() == 1
    engine.dispose()


def test_recognition_flow_is_tenant_isolated(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'recognition-tenant.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        user, community_a, _event = create_event_context(db)
        organization = __import__("src.models", fromlist=["Organization"]).Organization(
            owner_id=user.id, name="Second org", slug="second-org-flow")
        db.add(organization); db.flush()
        community_b = __import__("src.models", fromlist=["Community"]).Community(
            organization_id=organization.id, name="Second community", slug="second-community-flow")
        db.add(community_b); db.flush()
        db.add_all([
            AchievementRule(community_id=community_a.id, name="A rule", slug="a-rule-flow",
                            condition_tree={"operator": ">=", "metric": "impact_points", "value": 1},
                            reward_definition={"impact_points": 5}),
            AchievementRule(community_id=community_b.id, name="B rule", slug="b-rule-flow",
                            condition_tree={"operator": ">=", "metric": "impact_points", "value": 1},
                            reward_definition={"impact_points": 9}),
            ImpactTransaction(idempotency_key="tenant-flow", user_id=user.id, community_id=community_a.id,
                              points=1, source_type="test", reason="tenant", status=ImpactTransactionStatus.POSTED),
        ])
        db.commit()
        evaluate_recognition(db, user.id, community_a.id)
        evaluate_recognition(db, user.id, community_b.id)
        assert db.query(AchievementAward).filter_by(community_id=community_a.id).count() == 1
        assert db.query(AchievementAward).filter_by(community_id=community_b.id).count() == 0
        assert db.query(ImpactTransaction).filter_by(source_type="achievement_reward", community_id=community_b.id).count() == 0
    engine.dispose()
