"""Community activity service tests."""

from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import (
    ActivityStatus,
    EngagementDimension,
    Membership,
    MembershipRole,
    PointRule,
    User,
)
from src.services.activity import record_activity, verify_activity
from tests.test_database import create_event_context


def test_verified_service_activity_awards_configured_points(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'activity.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        organizer, community, _event = create_event_context(db)
        member = User(email="activity-member@example.com", password_hash="hash")
        db.add(member)
        db.flush()
        db.add_all(
            [
                Membership(
                    community_id=community.id,
                    user_id=organizer.id,
                    role=MembershipRole.ORGANIZER,
                ),
                PointRule(source_type="service_activity", points=15),
            ]
        )
        db.commit()
        activity = record_activity(
            db,
            member,
            community_id=community.id,
            activity_type="mentoring",
            dimension=EngagementDimension.SERVICE,
            description="Mentored a community member",
            occurred_at=datetime.now(UTC),
        )
        verify_activity(db, activity, organizer, True)
        assert activity.status == ActivityStatus.VERIFIED
        from src.models import ImpactTransaction

        assert db.query(ImpactTransaction).one().points == 15
    engine.dispose()
