"""Recognition engine tests."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import (
    ImpactTransaction,
    ImpactTransactionStatus,
    Milestone,
    MilestoneRequirement,
    Rank,
)
from src.services.recognition import current_rank, qualified_milestones
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
    engine.dispose()
