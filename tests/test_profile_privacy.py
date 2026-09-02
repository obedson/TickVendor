"""Profile updates and visibility policy tests."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import Membership, MembershipRole, Profile, ProfileVisibility, User
from src.security import create_access_token, hash_password
from tests.test_database import create_event_context


def _client(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'profile-privacy.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        owner, community, _event = create_event_context(db)
        member = User(email="member@example.com", password_hash=hash_password("password-password"))
        outsider = User(email="outsider@example.com", password_hash=hash_password("password-password"))
        db.add_all([member, outsider]); db.flush()
        db.add_all([
            Profile(user_id=member.id, username="member-viewer", display_name="Member Viewer"),
            Profile(user_id=outsider.id, username="outside-viewer", display_name="Outside Viewer"),
            Membership(community_id=community.id, user_id=owner.id, role=MembershipRole.MEMBER),
            Membership(community_id=community.id, user_id=member.id, role=MembershipRole.ORGANIZER),
        ])
        db.commit()
        ids = owner.id, member.id, outsider.id
    app = create_app()

    def override_get_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    return engine, TestClient(app), ids


def _headers(user_id):
    return {"Authorization": f"Bearer {create_access_token(user_id, 'participant')}"}


def test_owner_updates_profile_metadata_and_privacy(tmp_path):
    engine, client, (owner_id, _member_id, _outsider_id) = _client(tmp_path)
    response = client.patch(
        "/api/v1/profiles/me",
        headers=_headers(owner_id),
        json={
            "display_name": "Updated Owner",
            "bio": "Community volunteer",
            "location": "Abuja",
            "photo_url": "https://cdn.example/avatar.png",
            "visibility": "members",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "id": str(owner_id),
        "username": "owner",
        "display_name": "Updated Owner",
        "visibility": "members",
        "bio": "Community volunteer",
        "location": "Abuja",
        "photo_url": "https://cdn.example/avatar.png",
    }
    engine.dispose()


def test_member_visibility_requires_shared_active_community(tmp_path):
    engine, client, (owner_id, member_id, outsider_id) = _client(tmp_path)
    update = client.patch(
        "/api/v1/profiles/me", headers=_headers(owner_id), json={"visibility": "members"}
    )
    assert update.status_code == 200
    assert client.get(f"/api/v1/profiles/{owner_id}", headers=_headers(member_id)).status_code == 200
    assert client.get(f"/api/v1/profiles/{owner_id}", headers=_headers(outsider_id)).status_code == 404
    assert client.get(f"/api/v1/profiles/{owner_id}").status_code == 404
    engine.dispose()


def test_private_profile_is_hidden_but_owner_can_use_own_profile(tmp_path):
    engine, client, (owner_id, member_id, _outsider_id) = _client(tmp_path)
    assert client.patch(
        "/api/v1/profiles/me", headers=_headers(owner_id), json={"visibility": ProfileVisibility.PRIVATE.value}
    ).status_code == 200
    assert client.get(f"/api/v1/profiles/{owner_id}", headers=_headers(member_id)).status_code == 404
    assert client.get("/api/v1/profiles/me", headers=_headers(owner_id)).status_code == 200
    engine.dispose()
