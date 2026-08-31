"""Task and Impact Point service tests."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import (
    AuditLog,
    Membership,
    MembershipRole,
    Notification,
    PointRule,
    TaskAssignmentStatus,
    User,
)
from src.services.task import assign_task, create_task, submit_task, verify_task
from tests.test_database import create_event_context


def test_verified_task_awards_points_once(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'task.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        organizer, community, event = create_event_context(db)
        member = User(email="task-member@example.com", password_hash="hash")
        db.add(member); db.flush()
        db.add_all([
            Membership(community_id=community.id, user_id=organizer.id, role=MembershipRole.ORGANIZER),
            Membership(community_id=community.id, user_id=member.id, role=MembershipRole.MEMBER),
            PointRule(source_type="task_completion", points=20),
        ])
        db.commit()
        task = create_task(db, community.id, organizer, title="Do work", description="Complete work",
                           event_id=event.id, impact_point_reward=20)
        assignment = assign_task(db, task, member.id, organizer)
        submit_task(db, assignment, member, evidence_text="Done")
        verify_task(db, assignment, organizer, True)
        assert assignment.status == TaskAssignmentStatus.VERIFIED
        from src.models import ImpactTransaction
        assert db.query(ImpactTransaction).count() == 1
        assert db.query(AuditLog).filter_by(action="task.verified").one().actor_id == organizer.id
        assert db.query(Notification).filter_by(notification_type="task_verified").one().user_id == member.id
    engine.dispose()
