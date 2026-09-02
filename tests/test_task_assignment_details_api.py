"""Participant assignment detail API coverage."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import Membership, MembershipRole, Profile, Task, TaskAssignment, User
from src.security import create_access_token
from tests.test_database import create_event_context


def test_assignment_details_are_scoped_to_current_user(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'assignment-details.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine); sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        owner, community, event = create_event_context(db)
        member = User(email="assignment-member@example.com", password_hash="hashed")
        outsider = User(email="assignment-outsider@example.com", password_hash="hashed")
        db.add_all([member, outsider]); db.flush()
        db.add_all([Profile(user_id=member.id, username="assignment-member", display_name="Member"), Profile(user_id=outsider.id, username="assignment-outsider", display_name="Outsider"), Membership(community_id=community.id, user_id=member.id, role=MembershipRole.MEMBER)])
        task = Task(community_id=community.id, event_id=event.id, created_by_id=owner.id, title="Help", description="Help out")
        db.add(task); db.flush(); assignment = TaskAssignment(task_id=task.id, assignee_id=member.id, assigned_by_id=owner.id); db.add(assignment); db.commit(); member_id, outsider_id = member.id, outsider.id
    app = create_app()
    def override():
        with sessions() as db: yield db
    app.dependency_overrides[get_db] = override; client = TestClient(app)
    response = client.get("/api/v1/task-assignments/me/details", headers={"Authorization": f"Bearer {create_access_token(member_id, 'participant')}"})
    assert response.status_code == 200 and response.json()[0]["title"] == "Help"
    other = client.get("/api/v1/task-assignments/me/details", headers={"Authorization": f"Bearer {create_access_token(outsider_id, 'participant')}"})
    assert other.status_code == 200 and other.json() == []
    engine.dispose()
