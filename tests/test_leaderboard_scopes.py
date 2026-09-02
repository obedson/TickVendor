"""Leaderboard event and period scoring tests."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import (
    ImpactTransaction,
    ImpactTransactionStatus,
    Leaderboard,
    Membership,
    MembershipRole,
)
from src.services.leaderboard import leaderboard_entries
from tests.test_database import create_event_context


def test_event_and_period_scopes_exclude_unrelated_points(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'leaderboard-scopes.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        owner, community, event = create_event_context(db)
        owner.profile.username = "scoped-owner"
        db.add(Membership(community_id=community.id, user_id=owner.id, role=MembershipRole.MEMBER))
        from src.models import Event, EventStatus, LocationType
        other = Event(community_id=community.id, organizer_id=owner.id, title="Other", slug="other-scope",
                      description="Other", category="community", starts_at=datetime.now(UTC),
                      ends_at=datetime.now(UTC) + timedelta(hours=1), location_type=LocationType.ONLINE,
                      status=EventStatus.PUBLISHED)
        db.add(other); db.flush()
        now = datetime.now(UTC)
        board = Leaderboard(community_id=community.id, event_id=event.id, name="Event", slug="event-scope",
                            metric="overall", period="all_time", is_enabled=True)
        period = Leaderboard(community_id=community.id, name="Week", slug="week-scope",
                             metric="overall", period="weekly", is_enabled=True)
        db.add_all([board, period,
                    ImpactTransaction(idempotency_key="scope-event", user_id=owner.id, community_id=community.id,
                                      event_id=event.id, points=10, source_type="test", reason="event",
                                      status=ImpactTransactionStatus.POSTED, created_at=now),
                    ImpactTransaction(idempotency_key="scope-other", user_id=owner.id, community_id=community.id,
                                      event_id=other.id, points=20, source_type="test", reason="other",
                                      status=ImpactTransactionStatus.POSTED, created_at=now),
                    ImpactTransaction(idempotency_key="scope-old", user_id=owner.id, community_id=community.id,
                                      points=30, source_type="test", reason="old", status=ImpactTransactionStatus.POSTED,
                                      created_at=now - timedelta(days=10))])
        db.commit()
        assert leaderboard_entries(db, board, owner)[0]["score"] == 10
        assert leaderboard_entries(db, period, owner)[0]["score"] == 30
    engine.dispose()
