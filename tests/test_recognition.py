"""Recognition engine tests."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import (
    Activity,
    ActivityStatus,
    Attendance,
    AttendanceStatus,
    AuditLog,
    EngagementDimension,
    ImpactTransaction,
    ImpactTransactionStatus,
    Milestone,
    MilestoneRequirement,
    Notification,
    Rank,
    RankProgression,
    RankRequirement,
)
from src.services.recognition import (
    current_rank,
    evaluate_rank_progression,
    qualified_milestones,
    user_metrics,
)
from tests.test_database import create_event_context


def test_milestone_and_rank_qualification_are_database_configured(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'recognition.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        user, community, _event = create_event_context(db)
        milestone = Milestone(community_id=community.id, name="Builder", slug="builder")
        db.add(milestone); db.flush()
        db.add(MilestoneRequirement(milestone_id=milestone.id, metric="impact_points", operator=">=", threshold=100))
        db.add_all([
            Rank(community_id=community.id, name="Starter", slug="starter", minimum_points=0, sort_order=1),
            Rank(community_id=community.id, name="Builder", slug="rank-builder", minimum_points=100, sort_order=2),
            ImpactTransaction(idempotency_key="recognition-points", user_id=user.id, community_id=community.id,
                              points=120, source_type="manual", reason="Test", status=ImpactTransactionStatus.POSTED),
        ]); db.commit()
        assert [item.slug for item in qualified_milestones(db, user.id, community.id)] == ["builder"]
        assert current_rank(db, user.id, community.id).slug == "rank-builder"
        requirement = RankRequirement(rank_id=db.query(Rank).filter_by(slug="rank-builder").one().id,
                                      requirement_type="task_count", threshold=1)
        db.add(requirement); db.commit()
        assert current_rank(db, user.id, community.id).slug == "starter"
    engine.dispose()


def test_milestone_metrics_include_event_participation_and_consecutive_activity(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'recognition-activity.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        user, community, first_event = create_event_context(db)
        now = datetime.now(UTC)
        second_event = type(first_event)(
            community_id=community.id,
            organizer_id=user.id,
            title="Second Event",
            slug="second-event",
            description="A second event for metric coverage.",
            category="Community",
            starts_at=now,
            ends_at=now + timedelta(hours=1),
            location_type=first_event.location_type,
        )
        db.add(second_event)
        db.flush()
        db.add_all([
            Attendance(event_id=first_event.id, user_id=user.id, status=AttendanceStatus.GPS_VERIFIED),
            Attendance(event_id=second_event.id, user_id=user.id, status=AttendanceStatus.QR_VERIFIED),
            *[
                Activity(
                    community_id=community.id,
                    user_id=user.id,
                    activity_type="service",
                    dimension=EngagementDimension.SERVICE,
                    status=ActivityStatus.VERIFIED,
                    occurred_at=now - timedelta(days=day),
                )
                for day in (0, 1, 2, 4)
            ],
        ])
        db.commit()

        metrics = user_metrics(db, user.id, community.id)

        assert metrics["event_participation"] == 2
        assert metrics["consecutive_activities"] == 3
    engine.dispose()


def test_rank_progression_has_no_effect_without_qualification(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'rank-none.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        user, community, _event = create_event_context(db)
        rank = Rank(community_id=community.id, name="Builder", slug="builder-none", minimum_points=100, sort_order=1)
        db.add(rank); db.flush()
        db.add(RankRequirement(rank_id=rank.id, requirement_type="task_count", threshold=1)); db.commit()
        assert evaluate_rank_progression(db, user.id, community.id) is None
        assert db.query(RankProgression).count() == 0
        assert db.query(AuditLog).filter_by(action="rank.achieved").count() == 0
        assert db.query(Notification).filter_by(notification_type="rank_achieved").count() == 0
    engine.dispose()


def test_rank_progression_initial_unchanged_and_upward_are_exactly_once(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'rank-history.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        user, community, _event = create_event_context(db)
        starter = Rank(community_id=community.id, name="Starter", slug="starter-history", minimum_points=0, sort_order=1)
        builder = Rank(community_id=community.id, name="Builder", slug="builder-history", minimum_points=50, sort_order=2)
        db.add_all([starter, builder]); db.commit()
        assert evaluate_rank_progression(db, user.id, community.id).slug == starter.slug
        evaluate_rank_progression(db, user.id, community.id)
        assert db.query(RankProgression).count() == 1
        db.add(ImpactTransaction(idempotency_key="rank-history-points", user_id=user.id, community_id=community.id,
                                 points=50, source_type="test", reason="rank", status=ImpactTransactionStatus.POSTED))
        db.commit()
        assert evaluate_rank_progression(db, user.id, community.id).slug == builder.slug
        evaluate_rank_progression(db, user.id, community.id)
        assert db.query(RankProgression).count() == 2
        assert db.query(AuditLog).filter_by(action="rank.achieved").count() == 2
        assert db.query(Notification).filter_by(notification_type="rank_achieved").count() == 2
    engine.dispose()


def test_rank_progression_honors_non_point_requirements(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'rank-requirements.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        user, community, event = create_event_context(db)
        rank = Rank(community_id=community.id, name="Service", slug="service-rank", minimum_points=50, sort_order=1)
        db.add(rank); db.flush()
        db.add_all([RankRequirement(rank_id=rank.id, requirement_type="attendance_count", threshold=1),
                    ImpactTransaction(idempotency_key="rank-points", user_id=user.id, community_id=community.id,
                                      points=100, source_type="test", reason="rank", status=ImpactTransactionStatus.POSTED)])
        db.commit()
        assert current_rank(db, user.id, community.id) is None
        db.add(Attendance(event_id=event.id, user_id=user.id, status=AttendanceStatus.GPS_VERIFIED)); db.commit()
        assert evaluate_rank_progression(db, user.id, community.id).slug == rank.slug
    engine.dispose()
