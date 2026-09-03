from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import Membership, MembershipRole, Ticket, TicketStatus, TicketType
from src.security import create_access_token
from tests.test_database import create_event_context


def test_organizer_ticket_validation_returns_valid_and_rejects_wrong_event(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'attendance-ops.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        organizer, community, event = create_event_context(db)
        db.add(Membership(community_id=community.id, user_id=organizer.id, role=MembershipRole.ORGANIZER))
        ticket_type = TicketType(event_id=event.id, name="Operations", price=0, quantity=10)
        db.add(ticket_type); db.flush()
        ticket = Ticket(event_id=event.id, ticket_type_id=ticket_type.id, attendee_id=organizer.id,
                        public_id="OPS-TICKET-0000000000000001", qr_token="ops-valid-qr-token-000000000000000000000000000000000000", status=TicketStatus.ACTIVE)
        db.add(ticket); db.commit(); organizer_id, event_id, ticket_id = organizer.id, event.id, ticket.id
    app = create_app()
    def override():
        with sessions() as db: yield db
    app.dependency_overrides[get_db] = override
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {create_access_token(organizer_id, 'organizer')}"}
    valid = client.post(f"/api/v1/events/{event_id}/tickets/validate", headers=headers, json={"qr_token": ticket.qr_token})
    assert valid.status_code == 200 and valid.json()["result"] == "valid"
    wrong = client.post(f"/api/v1/events/{event_id}/tickets/validate", headers=headers, json={"qr_token": ticket.qr_token})
    assert wrong.status_code == 200 and wrong.json()["result"] == "already_used"
    with sessions() as db:
        assert db.get(Ticket, ticket_id).status == TicketStatus.USED
    engine.dispose()
