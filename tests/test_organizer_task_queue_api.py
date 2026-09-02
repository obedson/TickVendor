"""Organizer task verification queue API tests."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import (
    Membership,
    MembershipRole,
    Task,
    TaskAssignment,
    TaskAssignmentStatus,
    TaskSubmission,
    User,
)
from src.security import create_access_token
from tests.test_database import create_event_context


def test_organizer_can_list_submitted_task_evidence_for_owned_community(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'task-queue.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        organizer, community, event = create_event_context(db)
        member = User(email="queue-member@example.com", password_hash="hash")
        db.add(member); db.flush()
        db.add_all([
            Membership(community_id=community.id, user_id=organizer.id, role=MembershipRole.ORGANIZER),
            Membership(community_id=community.id, user_id=member.id, role=MembershipRole.MEMBER),
        ])
        task = Task(community_id=community.id, event_id=event.id, created_by_id=organizer.id,
                    title="Queue task", description="Review this evidence", impact_point_reward=4)
        db.add(task); db.flush()
        assignment = TaskAssignment(task_id=task.id, assignee_id=member.id, assigned_by_id=organizer.id,
                                    status=TaskAssignmentStatus.SUBMITTED)
        db.add(assignment); db.flush()
        db.add(TaskSubmission(assignment_id=assignment.id, evidence_text="Evidence body", submitted_at=datetime.now(UTC)))
        db.commit()
        organizer_id, community_id = organizer.id, community.id
    app = create_app()
    def override():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = override
    response = TestClient(app).get(
        f"/api/v1/communities/{community_id}/task-verification-queue",
        headers={"Authorization": f"Bearer {create_access_token(organizer_id, 'organizer')}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 1
    assert body[0]["task_title"] == "Queue task"
    assert body[0]["evidence_text"] == "Evidence body"
    assert "password" not in str(body[0]).lower()
    engine.dispose()


def test_member_cannot_list_task_verification_queue(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'task-queue-denied.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        _organizer, community, _event = create_event_context(db)
        member = User(email="queue-denied@example.com", password_hash="hash")
        db.add(member); db.flush()
        db.add(Membership(community_id=community.id, user_id=member.id, role=MembershipRole.MEMBER))
        db.commit()
        member_id, community_id = member.id, community.id
    app = create_app()
    def override():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = override
    response = TestClient(app).get(
        f"/api/v1/communities/{community_id}/task-verification-queue",
        headers={"Authorization": f"Bearer {create_access_token(member_id, 'participant')}"},
    )
    assert response.status_code == 403
    engine.dispose()
