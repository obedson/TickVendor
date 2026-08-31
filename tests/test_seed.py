"""Seed behavior tests."""

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import ContributionBand, EventCategory, PointRule
from src.seed import seed_business_configuration


def test_business_configuration_seed_is_database_backed_and_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'seed.db'}")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        seed_business_configuration(session)
        seed_business_configuration(session)
        assert session.scalar(select(func.count()).select_from(EventCategory)) == 13
        assert session.scalar(select(func.count()).select_from(PointRule)) == 5
        assert session.scalar(select(func.count()).select_from(ContributionBand)) == 4

    engine.dispose()
