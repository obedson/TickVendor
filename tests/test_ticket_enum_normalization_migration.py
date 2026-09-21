"""Regression coverage for legacy lowercase ticket/entitlement enum storage."""

from datetime import UTC, datetime, timedelta
from io import StringIO
from uuid import uuid4

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from src.config import settings
from src.database import get_db
from src.main import create_app
from src.models import (
    Community,
    Entitlement,
    EntitlementRedemption,
    Event,
    EventStatus,
    LocationType,
    RedemptionMode,
    RedemptionStatus,
    Ticket,
    TicketAssignmentState,
    TicketEntitlement,
    TicketEntitlementStatus,
    TicketStatus,
    TicketTransfer,
    TicketType,
    TransferStatus,
    User,
)
from src.security import create_access_token
from tests.test_task_evidence_migration import test_populated_upgrade_preserves_history


def _prepare_legacy_database(tmp_path, monkeypatch):
    # This helper leaves a populated database at c8d9e0f12345. Advancing through
    # b3c4d5e6f7a8 reproduces the deployed lowercase defaults on real rows.
    test_populated_upgrade_preserves_history(tmp_path, monkeypatch)
    config = Config("alembic.ini")
    command.upgrade(config, "c1d2e3f4a5b6")
    engine = sa.create_engine(settings.database_url)
    now = datetime.now(UTC)
    ids = {name: str(uuid4()) for name in ("unassigned", "invitation", "default", "entitlement", "ticket_entitlement", "redemption", "transfer")}
    with Session(engine, expire_on_commit=False) as db:
        user = db.scalars(sa.select(User)).first()
        community = db.scalars(sa.select(Community)).first()
        event = Event(community_id=community.id, organizer_id=user.id, title="Legacy wallet event",
                      slug=f"legacy-wallet-{uuid4().hex[:8]}", description="Migration fixture event",
                      category="community", starts_at=now + timedelta(days=1),
                      ends_at=now + timedelta(days=1, hours=2), location_type=LocationType.ONLINE,
                      online_url="https://example.test/event", status=EventStatus.PUBLISHED)
        db.add(event); db.flush()
        ticket_type = TicketType(event_id=event.id, name="Legacy ticket", price=0, quantity=10,
                                 max_per_user=1, max_per_order=1)
        db.add(ticket_type); db.flush()
        ticket_model = Ticket(public_id=f"legacy-{uuid4().hex[:10]}", qr_token=f"legacy-qr-{uuid4()}",
                              event_id=event.id, ticket_type_id=ticket_type.id, attendee_id=user.id,
                              purchaser_id=user.id, assignment_state=TicketAssignmentState.CLAIMED,
                              status=TicketStatus.ACTIVE)
        db.add(ticket_model); db.commit()
        ticket = {"id": str(ticket_model.id), "attendee_id": str(user.id), "event_id": str(event.id),
                  "ticket_type_id": str(ticket_type.id)}
    with engine.begin() as connection:
        user_id = ticket["attendee_id"]
        event_id = ticket["event_id"]
        ticket_type_id = ticket["ticket_type_id"]
        connection.execute(sa.text(
            "UPDATE tickets SET assignment_state='claimed', status='ACTIVE', order_id=NULL "
            "WHERE id=:id"
        ), {"id": ticket["id"]})
        for key, state in (("unassigned", "unassigned"), ("invitation", "invitation_sent")):
            connection.execute(sa.text(
                "INSERT INTO tickets (id, public_id, qr_token, event_id, ticket_type_id, attendee_id, "
                "purchaser_id, order_id, assignment_state, status, created_at, updated_at) "
                "VALUES (:id, :public, :qr, :event, :type, :user, :user, NULL, :state, 'ACTIVE', :now, :now)"
            ), {"id": ids[key], "public": f"legacy-{key}", "qr": f"legacy-qr-{key}",
                "event": event_id, "type": ticket_type_id, "user": user_id, "state": state, "now": now})
        connection.execute(sa.text(
            "INSERT INTO entitlements (id,event_id,ticket_type_id,name,quantity,is_active,redemption_mode,"
            "requires_check_in,requires_checkout,requires_geofence,requires_staff_validation,one_time,"
            "max_redemptions_per_ticket,eligibility,created_by_id,created_at,updated_at) "
            "VALUES (:id,:event,:type,'Legacy perk',1,1,'either',0,0,0,1,1,1,'{}',:user,:now,:now)"
        ), {"id": ids["entitlement"], "event": event_id, "type": ticket_type_id, "user": user_id, "now": now})
        connection.execute(sa.text(
            "INSERT INTO ticket_entitlements (id,ticket_id,entitlement_id,quantity_total,quantity_redeemed,status,created_at,updated_at) "
            "VALUES (:id,:ticket,:entitlement,1,0,'available',:now,:now)"
        ), {"id": ids["ticket_entitlement"], "ticket": ticket["id"], "entitlement": ids["entitlement"], "now": now})
        connection.execute(sa.text(
            "INSERT INTO entitlement_redemptions (id,ticket_entitlement_id,event_id,ticket_id,entitlement_id,holder_id,"
            "code_hash,qr_token_hash,status,expires_at,created_at,updated_at) "
            "VALUES (:id,:te,:event,:ticket,:entitlement,:user,:code,:qr,'issued',:expires,:now,:now)"
        ), {"id": ids["redemption"], "te": ids["ticket_entitlement"], "event": event_id,
            "ticket": ticket["id"], "entitlement": ids["entitlement"], "user": user_id,
            "code": "a" * 64, "qr": "b" * 64, "expires": now + timedelta(hours=1), "now": now})
        connection.execute(sa.text(
            "INSERT INTO ticket_transfers (id,ticket_id,created_by_id,claim_token_hash,status,expires_at,created_at,updated_at) "
            "VALUES (:id,:ticket,:user,:token,'pending',:expires,:now,:now)"
        ), {"id": ids["transfer"], "ticket": ids["unassigned"], "user": user_id,
            "token": "c" * 64, "expires": now + timedelta(hours=1), "now": now})
    return config, engine, ids, ticket["id"], user_id, event_id, ticket_type_id


def test_legacy_enum_values_migrate_load_and_wallet_returns_200(tmp_path, monkeypatch):
    config, engine, ids, claimed_id, user_id, event_id, ticket_type_id = _prepare_legacy_database(tmp_path, monkeypatch)
    engine.dispose()
    command.upgrade(config, "head")
    engine = sa.create_engine(settings.database_url)

    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one() == "c4d5e6f7a8b9"
        stored = dict(connection.execute(sa.text("SELECT id, assignment_state FROM tickets")).tuples().all())
        assert stored[claimed_id] == "CLAIMED", stored
        assert stored[ids["unassigned"]] == "UNASSIGNED", stored
        assert stored[ids["invitation"]] == "INVITATION_SENT", stored

    with Session(engine) as db:
        assert db.get(Ticket, claimed_id).assignment_state is TicketAssignmentState.CLAIMED
        assert db.get(Ticket, ids["unassigned"]).assignment_state is TicketAssignmentState.UNASSIGNED
        assert db.get(Ticket, ids["invitation"]).assignment_state is TicketAssignmentState.INVITATION_SENT
        assert db.get(Entitlement, ids["entitlement"]).redemption_mode is RedemptionMode.EITHER
        assert db.get(TicketEntitlement, ids["ticket_entitlement"]).status is TicketEntitlementStatus.AVAILABLE
        assert db.get(EntitlementRedemption, ids["redemption"]).status is RedemptionStatus.ISSUED
        assert db.get(TicketTransfer, ids["transfer"]).status is TransferStatus.PENDING

    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()
    def override_db():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    response = TestClient(app).get(
        "/api/v1/tickets/me",
        headers={"Authorization": f"Bearer {create_access_token(user_id, 'participant')}"},
    )
    assert response.status_code == 200, response.text
    states = {item["assignment_state"] for item in response.json()}
    assert {"claimed", "unassigned", "invitation_sent"}.issubset(states)

    # A database-default insert now stores the canonical member name and is ORM-loadable.
    new_id = str(uuid4())
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO tickets (id,public_id,qr_token,event_id,ticket_type_id,attendee_id,purchaser_id,status,created_at,updated_at) "
            "VALUES (:id,:public,:qr,:event,:type,:user,:user,'ACTIVE',:now,:now)"
        ), {"id": new_id, "public": f"new-{new_id[:8]}", "qr": f"new-qr-{new_id}",
            "event": event_id, "type": ticket_type_id, "user": user_id, "now": now})
        assert connection.execute(sa.text("SELECT assignment_state FROM tickets WHERE id=:id"), {"id": new_id}).scalar_one() == "CLAIMED"
    with Session(engine) as db:
        assert db.get(Ticket, new_id).assignment_state is TicketAssignmentState.CLAIMED
    engine.dispose()


def test_normalization_preserves_already_canonical_values(tmp_path, monkeypatch):
    config, engine, _ids, claimed_id, *_ = _prepare_legacy_database(tmp_path, monkeypatch)
    with engine.begin() as connection:
        connection.execute(sa.text("UPDATE tickets SET assignment_state='CLAIMED' WHERE id=:id"), {"id": claimed_id})
    engine.dispose()
    command.upgrade(config, "head")
    engine = sa.create_engine(settings.database_url)
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT assignment_state FROM tickets WHERE id=:id"), {"id": claimed_id}).scalar_one() == "CLAIMED"
    engine.dispose()


def test_postgresql_normalization_sql_and_revision_graph(monkeypatch):
    script = ScriptDirectory.from_config(Config("alembic.ini"))
    assert script.get_heads() == ["c4d5e6f7a8b9"]
    assert script.get_revision("c4d5e6f7a8b9").down_revision == "c1d2e3f4a5b6"
    output = StringIO()
    monkeypatch.setattr(settings, "database_url", "postgresql://migration-test/unused")
    command.upgrade(Config("alembic.ini", output_buffer=output), "c1d2e3f4a5b6:c4d5e6f7a8b9", sql=True)
    sql = output.getvalue()
    for legacy, canonical in (("claimed", "CLAIMED"), ("unassigned", "UNASSIGNED"),
                              ("invitation_sent", "INVITATION_SENT"), ("pending", "PENDING"),
                              ("either", "EITHER"), ("available", "AVAILABLE"), ("issued", "ISSUED")):
        assert legacy in sql and canonical in sql
    assert "ALTER TABLE tickets ALTER COLUMN assignment_state SET DEFAULT 'CLAIMED'" in sql
    assert "purchaser_id" not in sql and "qr_token" not in sql and "impact_transactions" not in sql
