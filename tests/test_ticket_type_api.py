"""Public ticket inventory response tests."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import Membership, MembershipRole, TicketType, TicketVisibility
from src.security import create_access_token
from tests.test_database import create_event_context


def test_event_ticket_types_expose_only_public_inventory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'ticket-types-api.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with Session(engine) as db:
        user, community, event = create_event_context(db)
        db.add(Membership(community_id=community.id, user_id=user.id, role=MembershipRole.MEMBER))
        db.add_all([
            TicketType(event_id=event.id, name="Free", price=0, quantity=10, visibility=TicketVisibility.PUBLIC),
            TicketType(event_id=event.id, name="Invite", price=0, quantity=10, visibility=TicketVisibility.INVITE_ONLY),
        ])
        event.status = "published"
        db.commit(); user_id, event_id = user.id, event.id
    app = create_app()
    def override():
        with sessions() as db: yield db
    app.dependency_overrides[get_db] = override
    response = TestClient(app).get(f"/api/v1/events/{event_id}/ticket-types",
                                   headers={"Authorization": f"Bearer {create_access_token(user_id, 'participant')}"})
    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == ["Free"]
    engine.dispose()
