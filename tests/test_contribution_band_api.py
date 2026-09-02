"""Contribution reward-band administration API tests."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import Membership, MembershipRole, User
from src.security import create_access_token, hash_password
from tests.test_database import create_event_context


def test_admin_can_create_band_and_member_is_denied(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'bands-api.db'}", connect_args={"check_same_thread": False}); Base.metadata.create_all(engine); sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        admin, community, _event = create_event_context(db); member = User(email="band-member@example.com", password_hash=hash_password("password-password")); db.add(member); db.flush(); db.add_all([Membership(community_id=community.id, user_id=admin.id, role=MembershipRole.ADMIN), Membership(community_id=community.id, user_id=member.id)]); db.commit(); ids = admin.id, member.id, community.id
    app = create_app()
    def override():
        with sessions() as db: yield db
    app.dependency_overrides[get_db] = override; client = TestClient(app); admin, member, community = ids
    payload = {"currency": "NGN", "minimum_amount": "1000", "maximum_amount": "5000", "points": 15, "per_user_period_cap": 100, "is_active": True}
    response = client.post(f"/api/v1/admin/communities/{community}/contribution-bands", headers={"Authorization": f"Bearer {create_access_token(admin, 'participant')}"}, json=payload)
    assert response.status_code == 201, response.text
    assert client.post(f"/api/v1/admin/communities/{community}/contribution-bands", headers={"Authorization": f"Bearer {create_access_token(member, 'participant')}"}, json=payload).status_code == 403
    engine.dispose()
