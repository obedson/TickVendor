"""Community and membership management API tests."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import (
    Community,
    Membership,
    MembershipRole,
    Organization,
    Profile,
    ProfileVisibility,
    User,
)
from src.security import create_access_token, hash_password


def setup(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'community-api.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine); sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        verified = datetime.now(UTC)
        admin = User(email="admin@example.com", password_hash=hash_password("password-password"), email_verified_at=verified)
        member = User(email="member@example.com", password_hash=hash_password("password-password"), email_verified_at=verified)
        outsider = User(email="outsider@example.com", password_hash=hash_password("password-password"), email_verified_at=verified)
        db.add_all([admin, member, outsider]); db.flush()
        db.add_all([Profile(user_id=admin.id, username="community-admin", display_name="Admin"),
                    Profile(user_id=member.id, username="community-member", display_name="Member"),
                    Profile(user_id=outsider.id, username="community-outsider", display_name="Outsider")])
        org = Organization(owner_id=admin.id, name="Org", slug="community-api-org")
        db.add(org); db.flush(); community = Community(organization_id=org.id, name="API Community", slug="community-api")
        db.add(community); db.flush()
        db.add_all([Membership(community_id=community.id, user_id=admin.id, role=MembershipRole.ADMIN),
                    Membership(community_id=community.id, user_id=member.id, role=MembershipRole.MEMBER)])
        db.commit(); ids = admin.id, member.id, outsider.id, community.id
    app = create_app()
    def override():
        with sessions() as db: yield db
    app.dependency_overrides[get_db] = override
    return engine, TestClient(app), ids, sessions


def headers(user_id): return {"Authorization": f"Bearer {create_access_token(user_id, 'participant')}"}


def test_admin_can_update_and_manage_members_with_audit(tmp_path):
    engine, client, (admin, _member, outsider, community), sessions = setup(tmp_path)
    response = client.patch(f"/api/v1/communities/{community}", headers=headers(admin), json={"description": "Updated", "logo_url": "https://cdn/logo.png"})
    assert response.status_code == 200 and response.json()["description"] == "Updated"
    added = client.post(f"/api/v1/communities/{community}/members", headers=headers(admin), json={"user_id": str(outsider), "role": "member"})
    assert added.status_code == 201
    membership_id = added.json()["id"]
    assert client.post(f"/api/v1/communities/{community}/membership/accept", headers=headers(outsider)).status_code == 200
    assert client.patch(f"/api/v1/communities/{community}/members/{membership_id}/role", headers=headers(admin), json={"role": "organizer", "reason": "Organize community events"}).status_code == 200
    assert client.patch(f"/api/v1/communities/{community}/members/{membership_id}/status", headers=headers(admin), json={"status": "active", "reason": "Keep membership active"}).status_code == 200
    with sessions() as db:
        assert db.query(Membership).filter_by(id=membership_id).one().status == __import__("src.models", fromlist=["MembershipStatus"]).MembershipStatus.ACTIVE
        assert db.query(__import__("src.models", fromlist=["AuditLog"]).AuditLog).filter_by(community_id=community).count() >= 3
    engine.dispose()


def test_member_and_cross_community_users_are_denied_management(tmp_path):
    engine, client, (_admin, member, outsider, community), _sessions = setup(tmp_path)
    assert client.patch(f"/api/v1/communities/{community}", headers=headers(member), json={"name": "Nope"}).status_code == 403
    assert client.post(f"/api/v1/communities/{community}/members", headers=headers(member), json={"user_id": str(outsider)}).status_code == 403
    assert client.get(f"/api/v1/communities/{community}/members", headers=headers(outsider)).status_code == 403
    assert client.patch(f"/api/v1/communities/{community}", json={"name": "Nope"}).status_code in (401, 403)
    engine.dispose()


def test_member_listing_honors_private_profile(tmp_path):
    engine, client, (admin, member, _outsider, community), sessions = setup(tmp_path)
    with sessions() as db:
        db.query(Profile).filter_by(user_id=member).one().visibility = ProfileVisibility.PRIVATE; db.commit()
    response = client.get(f"/api/v1/communities/{community}/members", headers=headers(admin))
    item = next(item for item in response.json()["members"] if item["user_id"] == str(member))
    assert "display_name" not in item and "photo_url" not in item
    engine.dispose()
