"""Organizer dashboard aggregation tests."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
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
