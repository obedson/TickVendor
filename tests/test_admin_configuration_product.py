"""Admin configuration API tests."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import (
    Membership,
    MembershipRole,
    Organization,
    PointCeiling,
    PointRule,
    Profile,
    User,
)
from src.security import create_access_token, hash_password


def setup(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'admin-config.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine); sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        admin = User(email="config-admin@example.com", password_hash=hash_password("password-password")); member = User(email="config-member@example.com", password_hash=hash_password("password-password")); db.add_all([admin, member]); db.flush()
        db.add_all([Profile(user_id=admin.id, username="config-admin", display_name="Admin"), Profile(user_id=member.id, username="config-member", display_name="Member")])
        org = Organization(owner_id=admin.id, name="Config Org", slug="config-org"); db.add(org); db.flush()
        from src.models import Community
        community = Community(organization_id=org.id, name="Config Community", slug="config-community"); db.add(community); db.flush(); db.add_all([Membership(community_id=community.id, user_id=admin.id, role=MembershipRole.ADMIN), Membership(community_id=community.id, user_id=member.id)]); db.commit(); ids = admin.id, member.id, community.id
    app = create_app()
    def override():
        with sessions() as db: yield db
    app.dependency_overrides[get_db] = override
    return engine, TestClient(app), ids, sessions


def headers(uid): return {"Authorization": f"Bearer {create_access_token(uid, 'participant')}"}


def test_admin_can_upsert_point_rule_and_adjust_points(tmp_path):
    engine, client, (admin, member, community), sessions = setup(tmp_path)
    with sessions() as db:
        db.add(PointCeiling(source_type="task", maximum_points=12)); db.commit()
    response = client.put(f"/api/v1/admin/communities/{community}/point-rules", headers=headers(admin), json={"source_type": "task", "points": 12, "max_awards_per_user": 3})
    assert response.status_code == 200 and response.json()["points"] == 12
    adjustment = client.post(f"/api/v1/admin/communities/{community}/point-adjustments", headers=headers(admin), json={"target_user_id": str(member), "amount": 7, "reason": "Correction"})
    assert adjustment.status_code == 200
    with sessions() as db: assert db.query(PointRule).filter_by(community_id=community, source_type="task").one().points == 12
    engine.dispose()


def test_member_cannot_change_rules_or_adjust_points(tmp_path):
    engine, client, (_admin, member, community), _sessions = setup(tmp_path)
    assert client.put(f"/api/v1/admin/communities/{community}/point-rules", headers=headers(member), json={"source_type": "task", "points": 12}).status_code == 403
    assert client.post(f"/api/v1/admin/communities/{community}/point-adjustments", headers=headers(member), json={"target_user_id": str(member), "amount": 7, "reason": "Nope"}).status_code == 403
    engine.dispose()
