"""Tenant-isolated recognition metric tests."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import ImpactTransaction, ImpactTransactionStatus
from src.services.recognition import user_metrics
from tests.test_database import create_event_context


def test_user_metrics_are_isolated_by_community(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'metric-isolation.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        user, first_community, _event = create_event_context(db)
        from src.models import Community, Organization

        second_org = Organization(owner_id=user.id, name="Second", slug="second-metric-org")
        db.add(second_org)
        db.flush()
        second_community = Community(
            organization_id=second_org.id,
            name="Second community",
            slug="second-metric-community",
        )
        db.add(second_community)
        db.flush()
        db.add_all(
            [
                ImpactTransaction(
                    idempotency_key="first-community-points",
                    user_id=user.id,
                    community_id=first_community.id,
                    points=10,
                    source_type="test",
                    reason="First",
                    status=ImpactTransactionStatus.POSTED,
                ),
                ImpactTransaction(
                    idempotency_key="second-community-points",
                    user_id=user.id,
                    community_id=second_community.id,
                    points=200,
                    source_type="test",
                    reason="Second",
                    status=ImpactTransactionStatus.POSTED,
                ),
            ]
        )
        db.commit()
        assert user_metrics(db, user.id, first_community.id)["impact_points"] == 10
        assert user_metrics(db, user.id, second_community.id)["impact_points"] == 200
    engine.dispose()
