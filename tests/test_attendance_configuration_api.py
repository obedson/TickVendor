"""Attendance configuration API tests."""


from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import Membership, MembershipRole, User
from src.security import create_access_token, hash_password
from tests.test_database import create_event_context


def test_admin_can_update_attendance_configuration_and_member_is_denied(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'attendance-config.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine); sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        admin, community, event = create_event_context(db)
        member = User(email="attendance-member@example.com", password_hash=hash_password("password-password")); db.add(member); db.flush()
        db.add_all([Membership(community_id=community.id, user_id=admin.id, role=MembershipRole.ADMIN), Membership(community_id=community.id, user_id=member.id)])
        db.commit(); ids = admin.id, member.id, community.id, event.id
    app = create_app()
    def override():
        with sessions() as db: yield db
    app.dependency_overrides[get_db] = override
    client = TestClient(app); admin, member, community, event = ids
    payload = {"qr_attendance_enabled": True, "peer_confirmation_enabled": True, "confirmations_required": 1, "organizer_verification_enabled": True,
               "geofence_enabled": True, "geofence_radius_meters": 250, "max_peer_confirmations": 3,
               "peer_selection_limit": 4, "required_verification_methods": ["qr", "peer"]}
    response = client.patch(f"/api/v1/communities/{community}/events/{event}/attendance-config", headers={"Authorization": f"Bearer {create_access_token(admin, 'participant')}"}, json=payload)
    assert response.status_code == 200, response.text
    denied = client.patch(f"/api/v1/communities/{community}/events/{event}/attendance-config", headers={"Authorization": f"Bearer {create_access_token(member, 'participant')}"}, json=payload)
    assert denied.status_code == 403
    engine.dispose()


def test_peer_policy_requires_enabled_peer_and_sufficient_confirmations(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'peer-policy.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        admin, community, event = create_event_context(db)
        db.add(Membership(community_id=community.id, user_id=admin.id, role=MembershipRole.ADMIN))
        db.commit()
        ids = admin.id, community.id, event.id
    app = create_app()
    def override():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = override
    client = TestClient(app)
    admin, community, event = ids
    headers = {"Authorization": f"Bearer {create_access_token(admin, 'participant')}"}
    response = client.patch(
        f"/api/v1/communities/{community}/events/{event}/attendance-config",
        headers=headers,
        json={"required_verification_methods": ["peer"], "confirmations_required": 1},
    )
    assert response.status_code == 422
    response = client.patch(
        f"/api/v1/communities/{community}/events/{event}/attendance-config",
        headers=headers,
        json={"peer_confirmation_enabled": True, "required_verification_methods": ["peer"], "confirmations_required": 0},
    )
    assert response.status_code == 422
    response = client.patch(
        f"/api/v1/communities/{community}/events/{event}/attendance-config",
        headers=headers,
        json={"peer_confirmation_enabled": True, "required_verification_methods": ["peer"],
              "confirmations_required": 3, "max_peer_confirmations": 2},
    )
    assert response.status_code == 422
    engine.dispose()


def test_required_attendance_methods_must_be_enabled(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'required-methods.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        admin, community, event = create_event_context(db)
        db.add(Membership(community_id=community.id, user_id=admin.id, role=MembershipRole.ADMIN))
        db.commit()
        ids = admin.id, community.id, event.id
    app = create_app()
    def override():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = override
    client = TestClient(app)
    admin, community, event = ids
    headers = {"Authorization": f"Bearer {create_access_token(admin, 'participant')}"}
    for method, payload in (
        ("qr", {"required_verification_methods": ["qr"], "qr_attendance_enabled": False}),
        ("gps", {"required_verification_methods": ["gps"], "geofence_enabled": False}),
        ("organizer", {"required_verification_methods": ["organizer"], "organizer_verification_enabled": False}),
    ):
        response = client.patch(
            f"/api/v1/communities/{community}/events/{event}/attendance-config",
            headers=headers,
            json=payload,
        )
        assert response.status_code == 422, method
    engine.dispose()
