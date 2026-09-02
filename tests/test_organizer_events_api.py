"""Organizer event-management API tests."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import EventStatus, Membership, MembershipRole
from src.security import create_access_token
from tests.test_database import create_event_context


def test_organizer_can_list_only_owned_events(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'organizer-events.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        organizer, community, event = create_event_context(db)
        db.add(Membership(community_id=community.id, user_id=organizer.id, role=MembershipRole.ORGANIZER))
        event.status = EventStatus.PUBLISHED
        db.commit()
        organizer_id = organizer.id
    app = create_app()
    def override():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = override
    response = TestClient(app).get(
        "/api/v1/communities/organizer/events",
        headers={"Authorization": f"Bearer {create_access_token(organizer_id, 'organizer')}"},
    )
    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()] == [str(event.id)]
    engine.dispose()
