"""Admin service tests."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import AuditLog, Membership, MembershipRole, User
from src.services.admin import adjust_points
from tests.test_database import create_event_context


def test_manual_point_adjustment_is_audited(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'admin.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        admin, community, _event = create_event_context(db)
        target = User(email="target@example.com", password_hash="hash")
        db.add(target); db.flush()
        db.add(Membership(community_id=community.id, user_id=admin.id, role=MembershipRole.ADMIN)); db.commit()
        transaction = adjust_points(db, community.id, target.id, 25, "Correction", admin)
        assert transaction.points == 25
        assert db.query(AuditLog).one().metadata_json["reason"] == "Correction"
    engine.dispose()
