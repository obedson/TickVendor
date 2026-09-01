"""Organizer dashboard aggregation tests."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import Badge, BadgeAward, Milestone, MilestoneAward, User
from src.services.analytics import organizer_summary
from tests.test_database import create_event_context


def test_organizer_dashboard_returns_complete_empty_safe_metrics(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'organizer-dashboard.db'}");Base.metadata.create_all(engine)
    with Session(engine,expire_on_commit=False) as db:
        owner,_community,event=create_event_context(db);event.starts_at=datetime.now(UTC)+timedelta(days=1);event.ends_at=event.starts_at+timedelta(hours=2);db.commit()
        summary=organizer_summary(db,owner)
        assert summary['upcoming_events']==1
        assert summary['total_events']==1
        assert summary['revenue']=='0.00'
        assert summary['top_participants']==[]
    engine.dispose()


def test_organizer_dashboard_includes_achievement_distribution(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'organizer-achievements.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        owner, community, _event = create_event_context(db)
        attendee = User(email="dashboard-attendee@example.com", password_hash="hash")
        badge = Badge(
            community_id=community.id,
            name="First Step",
            slug="first-step",
            category="attendance",
            requirements={},
        )
        milestone = Milestone(
            community_id=community.id,
            name="Builder",
            slug="builder",
        )
        db.add_all([attendee, badge, milestone])
        db.flush()
        now = datetime.now(UTC)
        db.add_all([
            BadgeAward(
                badge_id=badge.id,
                user_id=attendee.id,
                idempotency_key="dashboard-badge",
                awarded_at=now,
            ),
            MilestoneAward(
                milestone_id=milestone.id,
                user_id=attendee.id,
                idempotency_key="dashboard-milestone",
                awarded_at=now,
            ),
        ])
        db.commit()

        summary = organizer_summary(db, owner)

        assert summary["achievement_distribution"] == {
            "badges": [{"name": "First Step", "awards": 1}],
            "milestones": [{"name": "Builder", "awards": 1}],
        }
    engine.dispose()
