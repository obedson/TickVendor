"""Audit query API tests."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import AuditLog, Community, Membership, MembershipRole, Organization, Profile, User
from src.security import create_access_token, hash_password


def test_admin_can_filter_audit_logs_and_sensitive_values_are_redacted(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'audit-api.db'}", connect_args={"check_same_thread": False}); Base.metadata.create_all(engine); sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        admin = User(email="audit-admin@example.com", password_hash=hash_password("password-password")); member = User(email="audit-member@example.com", password_hash=hash_password("password-password")); outsider = User(email="audit-outsider@example.com", password_hash=hash_password("password-password")); db.add_all([admin, member, outsider]); db.flush(); db.add_all([Profile(user_id=admin.id, username="audit-admin", display_name="Admin"), Profile(user_id=member.id, username="audit-member", display_name="Member"), Profile(user_id=outsider.id, username="audit-outsider", display_name="Outsider")]); org = Organization(owner_id=admin.id, name="Audit Org", slug="audit-org"); db.add(org); db.flush()
        community = Community(organization_id=org.id, name="Audit Community", slug="audit-community"); db.add(community); db.flush(); db.add(Membership(community_id=community.id, user_id=admin.id, role=MembershipRole.ADMIN)); db.add_all([AuditLog(actor_id=admin.id, community_id=community.id, action="point_rule.updated", target_type="point_rule", target_id=admin.id, metadata_json={"secret": "hide", "fields": ["points"]}, occurred_at=datetime.now(UTC)), AuditLog(actor_id=admin.id, community_id=community.id, action="membership.invited", target_type="membership", target_id=member.id, metadata_json={}, occurred_at=datetime.now(UTC) - timedelta(days=1))]); db.commit(); ids = admin.id, member.id, outsider.id, community.id
    app = create_app()
    def override():
        with sessions() as db: yield db
    app.dependency_overrides[get_db] = override; client = TestClient(app); admin, member, outsider, community = ids; headers = {"Authorization": f"Bearer {create_access_token(admin, 'participant')}"}
    response = client.get(f"/api/v1/admin/communities/{community}/audit-logs", headers=headers, params={"action": "point_rule.updated", "limit": 1})
    assert response.status_code == 200 and len(response.json()) == 1 and response.json()[0]["metadata"]["secret"] == "[REDACTED]"
    assert client.get(f"/api/v1/admin/communities/{community}/audit-logs", headers={"Authorization": f"Bearer {create_access_token(member, 'participant')}"}).status_code == 403
    assert client.get(f"/api/v1/admin/communities/{community}/audit-logs", headers={"Authorization": f"Bearer {create_access_token(outsider, 'participant')}"}).status_code == 403
    engine.dispose()
