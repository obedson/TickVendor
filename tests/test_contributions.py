"""Contribution reward tests."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import (
    ContributionBand,
    ContributionType,
    ImpactTransaction,
    Membership,
    MembershipRole,
    User,
)
from src.services.contribution import record_contribution, verify_contribution
from tests.test_database import create_event_context


def test_verified_contribution_uses_configurable_band(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'contribution.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        organizer, community, _event = create_event_context(db)
        contributor = User(email="contributor@example.com", password_hash="hash")
        db.add(contributor); db.flush()
        db.add_all([
            Membership(community_id=community.id, user_id=organizer.id, role=MembershipRole.ORGANIZER),
            ContributionBand(currency="NGN", minimum_amount=Decimal(1000), maximum_amount=Decimal("4999.99"), points=5),
        ]); db.commit()
        contribution = record_contribution(
            db, contributor, community_id=community.id, contribution_type=ContributionType.MONETARY,
            amount=Decimal(2000), currency="NGN", purpose="Support", occurred_at=datetime.now(UTC),
        )
        verify_contribution(db, contribution, organizer, True)
        transaction = db.query(ImpactTransaction).one()
        assert transaction.points == 5
    engine.dispose()
