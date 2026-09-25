"""Attendance configuration API tests."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import Event, Membership, MembershipRole, User
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
    with sessions() as db:
        from src.models import Event, Venue
        venue = Venue(name="Configured venue", address="Test venue", latitude=6.5, longitude=3.3)
        db.add(venue); db.flush(); db.get(Event, event).venue_id = venue.id; db.commit()
    payload = {"qr_attendance_enabled": True, "peer_confirmation_enabled": True, "confirmations_required": 1, "organizer_verification_enabled": True,
               "geofence_enabled": True, "geofence_radius_meters": 250, "geofence_max_accuracy_meters": 40,
               "max_peer_confirmations": 3,
               "peer_selection_limit": 4, "required_verification_methods": ["qr", "peer"]}
    response = client.patch(f"/api/v1/communities/{community}/events/{event}/attendance-config", headers={"Authorization": f"Bearer {create_access_token(admin, 'participant')}"}, json=payload)
    assert response.status_code == 200, response.text
    loaded = client.get(f"/api/v1/communities/{community}/events/{event}/attendance-config", headers={"Authorization": f"Bearer {create_access_token(admin, 'participant')}"})
    assert loaded.status_code == 200
    assert loaded.json()["required_verification_methods"] == ["qr", "peer"]
    assert loaded.json()["geofence_enabled"] is True
    assert loaded.json()["geofence_radius_meters"] == 250
    assert loaded.json()["geofence_max_accuracy_meters"] == 40
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


def attendance_client(tmp_path, name):
    """An admin-only client for one event, plus the ids, headers and session factory to drive it."""
    engine = create_engine(f"sqlite:///{tmp_path / name}", connect_args={"check_same_thread": False})
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
    admin, community, event = ids
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {create_access_token(admin, 'participant')}"}
    url = f"/api/v1/communities/{community}/events/{event}/attendance-config"
    return client, sessions, engine, event, headers, url


def test_self_checkout_is_rejected_when_stored_check_in_is_off(tmp_path):
    """A partial PATCH names only checkout; the guard must judge the merged state, not the payload."""
    client, sessions, engine, event, headers, url = attendance_client(tmp_path, "self-service-merged.db")
    response = client.patch(url, headers=headers, json={"self_checkout_enabled": True})
    assert response.status_code == 422, response.text
    with sessions() as db:
        stored = db.get(Event, event)
        assert stored.self_checkout_enabled is False
        assert stored.self_check_in_enabled is False
    engine.dispose()


def test_self_checkout_is_accepted_when_stored_check_in_is_on(tmp_path):
    client, sessions, engine, event, headers, url = attendance_client(tmp_path, "self-service-allowed.db")
    check_in = client.patch(url, headers=headers, json={"self_check_in_enabled": True})
    assert check_in.status_code == 200, check_in.text
    response = client.patch(url, headers=headers, json={"self_checkout_enabled": True})
    assert response.status_code == 200, response.text
    assert response.json()["self_checkout_enabled"] is True
    # Both halves in one payload are accepted too, and a null checkout window is a legal stored value.
    together = client.patch(url, headers=headers, json={"self_check_in_enabled": True, "self_checkout_enabled": True,
                                                        "checkout_opens_at": None})
    assert together.status_code == 200, together.text
    assert together.json()["checkout_opens_at"] is None
    with sessions() as db:
        stored = db.get(Event, event)
        assert stored.self_check_in_enabled is True
        assert stored.self_checkout_enabled is True
    engine.dispose()


def test_checkout_opens_at_round_trips_without_changing_the_utc_instant(tmp_path):
    client, sessions, engine, event, headers, url = attendance_client(tmp_path, "self-service-window.db")
    checkout_opens_at = datetime(2030, 6, 1, 14, 30, tzinfo=UTC)
    response = client.patch(
        url,
        headers=headers,
        json={
            "self_check_in_enabled": True,
            "self_checkout_enabled": True,
            "checkout_opens_at": checkout_opens_at.isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    assert datetime.fromisoformat(response.json()["checkout_opens_at"]) == checkout_opens_at

    loaded = client.get(url, headers=headers)
    assert loaded.status_code == 200, loaded.text
    loaded_checkout_opens_at = datetime.fromisoformat(loaded.json()["checkout_opens_at"])
    # SQLite drops timezone metadata for DateTime columns; production PostgreSQL does not.
    if loaded_checkout_opens_at.tzinfo is None:
        loaded_checkout_opens_at = loaded_checkout_opens_at.replace(tzinfo=UTC)
    assert loaded_checkout_opens_at == checkout_opens_at
    with sessions() as db:
        stored = db.get(Event, event)
        assert stored.checkout_opens_at.replace(tzinfo=UTC) == checkout_opens_at
    engine.dispose()


def test_disabling_self_check_in_cannot_leave_checkout_enabled(tmp_path):
    client, sessions, engine, event, headers, url = attendance_client(tmp_path, "self-service-disabled.db")
    enabled = client.patch(url, headers=headers, json={"self_check_in_enabled": True, "self_checkout_enabled": True})
    assert enabled.status_code == 200, enabled.text
    response = client.patch(url, headers=headers, json={"self_check_in_enabled": False})
    assert response.status_code == 422, response.text
    with sessions() as db:
        stored = db.get(Event, event)
        assert stored.self_check_in_enabled is True
        assert stored.self_checkout_enabled is True
    # Naming both halves is how the pair comes down.
    together = client.patch(url, headers=headers, json={"self_check_in_enabled": False, "self_checkout_enabled": False,
                                                        "checkout_opens_at": None})
    assert together.status_code == 200, together.text
    with sessions() as db:
        stored = db.get(Event, event)
        assert stored.self_check_in_enabled is False
        assert stored.self_checkout_enabled is False
    engine.dispose()


def test_unrelated_partial_patch_preserves_valid_self_service_state(tmp_path):
    client, sessions, engine, event, headers, url = attendance_client(tmp_path, "self-service-unrelated.db")
    enabled = client.patch(url, headers=headers, json={"self_check_in_enabled": True, "self_checkout_enabled": True})
    assert enabled.status_code == 200, enabled.text
    response = client.patch(url, headers=headers, json={"geofence_radius_meters": 250})
    assert response.status_code == 200, response.text
    assert response.json()["geofence_radius_meters"] == 250
    # The PATCH response echoes only the fields it was sent, so read the whole config back.
    loaded = client.get(url, headers=headers)
    assert loaded.status_code == 200
    body = loaded.json()
    assert body["self_check_in_enabled"] is True
    assert body["self_checkout_enabled"] is True
    assert body["geofence_radius_meters"] == 250
    with sessions() as db:
        stored = db.get(Event, event)
        assert stored.self_check_in_enabled is True
        assert stored.self_checkout_enabled is True
    engine.dispose()


def test_self_service_guard_leaves_required_method_rule_unchanged(tmp_path):
    """The merged-state guard must not shadow the pre-existing verification-method rule."""
    client, sessions, engine, event, headers, url = attendance_client(tmp_path, "self-service-methods.db")
    enabled = client.patch(url, headers=headers, json={"self_check_in_enabled": True, "self_checkout_enabled": True})
    assert enabled.status_code == 200, enabled.text
    rejected = client.patch(url, headers=headers, json={"required_verification_methods": ["gps"]})
    assert rejected.status_code == 422, rejected.text
    accepted = client.patch(url, headers=headers, json={"required_verification_methods": ["qr"]})
    assert accepted.status_code == 200, accepted.text
    with sessions() as db:
        stored = db.get(Event, event)
        assert stored.required_verification_methods == ["qr"]
        assert stored.self_checkout_enabled is True
    engine.dispose()
