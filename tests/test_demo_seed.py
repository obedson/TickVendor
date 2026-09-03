"""Complete local demo seed coverage."""
import os

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from scripts.seed_demo import main
from src.database import Base
from src.models import Activity, Badge, Community, Event, Milestone, Rank, Task, TicketType, User


def test_demo_seed_is_idempotent_and_contains_named_core_entities(tmp_path, monkeypatch):
    database = tmp_path / "demo-seed.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database}")
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    main()
    main()
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 3
        assert db.scalar(select(func.count()).select_from(Community)) == 1
        assert db.scalar(select(func.count()).select_from(Event)) == 1
        assert db.scalar(select(func.count()).select_from(TicketType)) == 1
        assert db.scalar(select(func.count()).select_from(Task)) == 1
        assert db.scalar(select(func.count()).select_from(Activity)) == 1
        assert db.scalar(select(func.count()).select_from(Badge)) == 8
        assert db.scalar(select(func.count()).select_from(Rank)) == 6
        assert db.scalar(select(func.count()).select_from(Milestone)) == 1
    engine.dispose()
