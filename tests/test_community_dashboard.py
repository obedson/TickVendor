"""Community dashboard analytics tests."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import (
    Attendance,
    AttendanceStatus,
    Badge,
    BadgeAward,
    Membership,
    MembershipRole,
    MembershipStatus,
    Rank,
    User,
)
from src.services.analytics import community_summary
from tests.test_database import create_event_context


def test_community_dashboard_includes_distributions_trends_and_retention(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'community-dashboard.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        owner, community, _event = create_event_context(db)
        member = User(email="community-dashboard@example.com", password_hash="hash")
        db.add(member)
        db.flush()
        now = datetime.now(UTC)
        db.add_all([
            Membership(
                community_id=community.id,
                user_id=owner.id,
                role=MembershipRole.ADMIN,
                status=MembershipStatus.ACTIVE,
                joined_at=now - timedelta(days=40),
            ),
            Membership(
                community_id=community.id,
                user_id=member.id,
                status=MembershipStatus.ACTIVE,
                joined_at=now - timedelta(days=10),
            ),
        ])
        badge = Badge(
            community_id=community.id,
            name="First Step",
            slug="first-step",
            category="attendance",
            requirements={},
        )
        rank = Rank(
            community_id=community.id,
            name="Starter",
            slug="starter",
            minimum_points=0,
            sort_order=1,
        )
        db.add_all([badge, rank])
        db.flush()
        db.add(BadgeAward(
            badge_id=badge.id,
            user_id=member.id,
            idempotency_key="community-dashboard-badge",
            awarded_at=now,
        ))
        db.add(Attendance(
            event_id=_event.id,
            user_id=member.id,
            status=AttendanceStatus.GPS_VERIFIED,
            checked_in_at=now,
        ))
        db.commit()

        summary = community_summary(db, community.id, owner)

        assert summary["active_members"] == 2
        assert summary["badge_distribution"] == [{"name": "First Step", "awards": 1}]
        assert summary["rank_distribution"] == [{"name": "Starter", "members": 2}]
        assert summary["participation_trends"] == [
            {"period": now.strftime("%Y-%m"), "attendances": 1}
        ]
        assert summary["retention"] == {"eligible_members": 1, "retained_members": 0, "rate": 0.0}
    engine.dispose()
