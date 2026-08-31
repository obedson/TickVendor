"""Leaderboard service tests."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import (
    Attendance,
    AttendanceStatus,
    ImpactTransaction,
    ImpactTransactionStatus,
    Leaderboard,
    Membership,
    MembershipRole,
)
from src.services.leaderboard import leaderboard_entries
from tests.test_database import create_event_context


def test_enabled_overall_leaderboard_excludes_money_specific_metric(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'leaderboard.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        owner, community, _event = create_event_context(db)
        owner.profile.username = "leader-owner"
        owner.profile.display_name = "Owner"
        db.add(Membership(community_id=community.id, user_id=owner.id, role=MembershipRole.MEMBER))
        board = Leaderboard(
            community_id=community.id,
            name="Overall",
            slug="overall",
            metric="overall",
            period="all_time",
            is_enabled=True,
        )
        db.add_all(
            [
                board,
                ImpactTransaction(
                    idempotency_key="leaderboard-points",
                    user_id=owner.id,
                    community_id=community.id,
                    points=50,
                    source_type="attendance",
                    reason="Attendance",
                    status=ImpactTransactionStatus.POSTED,
                ),
            ]
        )
        db.commit()
        assert leaderboard_entries(db, board, owner)[0]["score"] == 50
        attendance_board = Leaderboard(community_id=community.id, name="Attendance",
                                       slug="attendance", metric="attendance", period="all_time",
                                       is_enabled=True)
        db.add_all([attendance_board, Attendance(event_id=_event.id, user_id=owner.id,
                                                 status=AttendanceStatus.GPS_VERIFIED)])
        db.commit()
        assert leaderboard_entries(db, attendance_board, owner)[0]["score"] == 1
        board.is_enabled = False
        db.commit()
        assert leaderboard_entries(db, board, owner) == []
    engine.dispose()
