"""Task and Impact Point service tests."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
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
from src.services.task import (
    assign_task,
    create_task,
    submit_task,
    transition_assignment,
    verify_task,
)
from tests.test_database import create_event_context


def _submitted_task(db):
    organizer, community, event = create_event_context(db)
    member = User(email="atomic-member@example.com", password_hash="hash")
    db.add(member); db.flush()
    db.add_all([
        Membership(community_id=community.id, user_id=organizer.id, role=MembershipRole.ORGANIZER),
        Membership(community_id=community.id, user_id=member.id, role=MembershipRole.MEMBER),
        PointRule(source_type="task_completion", points=20),
    ])
    db.commit()
    task = create_task(db, community.id, organizer, title="Atomic task", description="Complete atomically",
                       event_id=event.id, impact_point_reward=20)
    assignment = assign_task(db, task, member.id, organizer)
    transition_assignment(db, assignment, member, TaskAssignmentStatus.ACCEPTED)
    transition_assignment(db, assignment, member, TaskAssignmentStatus.IN_PROGRESS)
    submit_task(db, assignment, member, evidence_text="Evidence")
    return organizer, member, task, assignment


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
        transition_assignment(db, assignment, member, TaskAssignmentStatus.ACCEPTED)
        transition_assignment(db, assignment, member, TaskAssignmentStatus.IN_PROGRESS)
        submit_task(db, assignment, member, evidence_text="Done")
        verify_task(db, assignment, organizer, True)
        assert assignment.status == TaskAssignmentStatus.VERIFIED
        from src.models import ImpactTransaction
        assert db.query(ImpactTransaction).count() == 1
        assert db.query(AuditLog).filter_by(action="task.verified").one().actor_id == organizer.id
        assert db.query(Notification).filter_by(notification_type="task_verified").one().user_id == member.id
    engine.dispose()


@pytest.mark.parametrize("failure", ["reward", "audit", "notification"])
def test_task_verification_failure_rolls_back_all_primary_side_effects(tmp_path, monkeypatch, failure):
    engine = create_engine(f"sqlite:///{tmp_path / (failure + '-rollback.db')}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        organizer, _member, _task, assignment = _submitted_task(db)
        target = {"reward": "award_points", "audit": "audit", "notification": "notify"}[failure]
        monkeypatch.setattr(f"src.services.task.{target}", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError(f"{failure} failure")))
        with pytest.raises(RuntimeError):
            verify_task(db, assignment, organizer, True)
        db.rollback()
        assert db.get(type(assignment), assignment.id).status == TaskAssignmentStatus.SUBMITTED
        from src.models import ImpactTransaction
        assert db.query(ImpactTransaction).count() == 0
        assert db.query(AuditLog).filter_by(action="task.verified").count() == 0
        assert db.query(Notification).filter_by(notification_type="task_verified").count() == 0
        monkeypatch.undo()
        verify_task(db, assignment, organizer, True)
        assert db.query(ImpactTransaction).count() == 1
        assert db.query(AuditLog).filter_by(action="task.verified").count() == 1
        assert db.query(Notification).filter_by(notification_type="task_verified").count() == 1
    engine.dispose()


def test_recognition_failure_is_after_durable_task_transaction(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'recognition-boundary.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        organizer, _member, _task, assignment = _submitted_task(db)
        monkeypatch.setattr("src.services.task.evaluate_recognition", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("recognition failure")))
        with pytest.raises(RuntimeError):
            verify_task(db, assignment, organizer, True)
        db.rollback()
        assert db.get(type(assignment), assignment.id).status == TaskAssignmentStatus.VERIFIED
    engine.dispose()


def test_task_assignment_rejects_assignee_from_another_community(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'task-isolation.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        organizer, community, _event = create_event_context(db)
        outsider = User(email="task-outsider@example.com", password_hash="hash")
        db.add(outsider); db.commit()
        db.add(Membership(community_id=community.id, user_id=organizer.id, role=MembershipRole.ORGANIZER)); db.commit()
        task = create_task(db, community.id, organizer, title="Scoped", description="Scoped task")
        with pytest.raises(HTTPException) as denied:
            assign_task(db, task, outsider.id, organizer)
        assert denied.value.status_code == 404
    engine.dispose()


def test_task_submission_handles_sqlite_naive_due_datetime(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'task-naive-due.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        _organizer, member, task, assignment = _submitted_task(db)
        assignment.status = TaskAssignmentStatus.REJECTED
        task.due_at = datetime.now(UTC) + timedelta(days=1)
        db.commit()
        submission = submit_task(db, assignment, member, evidence_text="Retry evidence")
        assert submission is not None
    engine.dispose()
