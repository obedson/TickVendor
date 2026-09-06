"""Organization-scoped activity and volunteer opportunity API tests."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import Community, Membership, MembershipRole, Organization, PointRule, Profile, User
from src.security import create_access_token, hash_password


def setup(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'opportunities.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        admin = User(email="op-admin@example.com", password_hash=hash_password("password-password"))
        member = User(email="op-member@example.com", password_hash=hash_password("password-password"))
        outsider = User(email="op-outsider@example.com", password_hash=hash_password("password-password"))
        other_admin = User(email="op-other-admin@example.com", password_hash=hash_password("password-password"))
        db.add_all([admin, member, outsider, other_admin]); db.flush()
        db.add_all([Profile(user_id=user.id, username=user.email.split("@")[0], display_name=user.email) for user in [admin, member, outsider, other_admin]])
        org = Organization(owner_id=admin.id, name="Opportunity Org", slug="opportunity-org")
        other_org = Organization(owner_id=other_admin.id, name="Other Org", slug="other-opportunity-org")
        db.add_all([org, other_org]); db.flush()
        community = Community(organization_id=org.id, name="Opportunity Community", slug="opportunity-community")
        other_community = Community(organization_id=other_org.id, name="Other Community", slug="other-community")
        db.add_all([community, other_community]); db.flush()
        db.add_all([
            Membership(community_id=community.id, user_id=admin.id, role=MembershipRole.ADMIN),
            Membership(community_id=community.id, user_id=member.id, role=MembershipRole.MEMBER),
            Membership(community_id=other_community.id, user_id=other_admin.id, role=MembershipRole.ADMIN),
            PointRule(community_id=community.id, source_type="service_activity", points=15),
        ])
        db.commit()
        ids = admin.id, member.id, outsider.id, other_admin.id, community.id, other_community.id
    app = create_app()
    def override():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = override
    return engine, TestClient(app), ids


def headers(user_id):
    return {"Authorization": f"Bearer {create_access_token(user_id, 'participant')}"}


def payload(title="Neighborhood cleanup", capacity=2):
    now = datetime.now(UTC)
    return {"title": title, "description": "Join this community service opportunity.", "activity_type": "volunteer_work", "dimension": "service", "starts_at": (now + timedelta(days=2)).isoformat(), "ends_at": (now + timedelta(days=2, hours=2)).isoformat(), "location": "Community hall", "capacity": capacity}


def test_admin_can_create_publish_and_member_can_discover_and_join(tmp_path):
    engine, client, (admin, member, _outsider, _other_admin, community, _other_community) = setup(tmp_path)
    created = client.post(f"/api/v1/communities/{community}/activity-opportunities", headers=headers(admin), json=payload())
    assert created.status_code == 201, created.text
    opportunity_id = created.json()["id"]
    assert client.post(f"/api/v1/activity-opportunities/{opportunity_id}/publish", headers=headers(admin)).status_code == 200
    discovered = client.get("/api/v1/activity-opportunities", headers=headers(member))
    assert discovered.status_code == 200
    assert discovered.json()[0]["id"] == opportunity_id
    joined = client.post(f"/api/v1/activity-opportunities/{opportunity_id}/join", headers=headers(member))
    assert joined.status_code == 201, joined.text
    assert joined.json()["status"] == "registered"
    registration_id = joined.json()["id"]
    assert client.post(f"/api/v1/activity-opportunities/{opportunity_id}/complete", headers=headers(member)).json()["status"] == "completed"
    verified = client.post(f"/api/v1/activity-opportunities/{opportunity_id}/registrations/{registration_id}/verify?approve=true", headers=headers(admin))
    assert verified.status_code == 200 and verified.json()["status"] == "verified", verified.text
    engine.dispose()


def test_activity_opportunity_enforces_tenant_duplicate_and_capacity_boundaries(tmp_path):
    engine, client, (admin, member, outsider, other_admin, community, other_community) = setup(tmp_path)
    created = client.post(f"/api/v1/communities/{community}/activity-opportunities", headers=headers(admin), json=payload(capacity=1))
    opportunity_id = created.json()["id"]
    assert client.post(f"/api/v1/activity-opportunities/{opportunity_id}/publish", headers=headers(admin)).status_code == 200
    assert client.post(f"/api/v1/activity-opportunities/{opportunity_id}/join", headers=headers(member)).status_code == 201
    assert client.post(f"/api/v1/activity-opportunities/{opportunity_id}/join", headers=headers(member)).status_code == 409
    assert client.post(f"/api/v1/activity-opportunities/{opportunity_id}/join", headers=headers(outsider)).status_code == 403
    assert client.get(f"/api/v1/communities/{community}/activity-opportunities", headers=headers(other_admin)).status_code == 403
    assert client.patch(f"/api/v1/activity-opportunities/{opportunity_id}", headers=headers(other_admin), json={"title": "Nope"}).status_code == 403
    other = client.post(f"/api/v1/communities/{other_community}/activity-opportunities", headers=headers(other_admin), json=payload("Other opportunity"))
    assert other.status_code == 201
    engine.dispose()


def test_public_opportunity_is_discoverable_without_membership(tmp_path):
    engine, client, (admin, _member, outsider, _other_admin, community, _other_community) = setup(tmp_path)
    created = client.post(
        f"/api/v1/communities/{community}/activity-opportunities",
        headers=headers(admin), json={**payload("Public cleanup"), "members_only": False},
    )
    opportunity_id = created.json()["id"]
    assert client.post(f"/api/v1/activity-opportunities/{opportunity_id}/publish", headers=headers(admin)).status_code == 200
    discovered = client.get("/api/v1/activity-opportunities", headers=headers(outsider))
    assert discovered.status_code == 200
    assert [item["id"] for item in discovered.json()] == [opportunity_id]
    assert client.post(f"/api/v1/activity-opportunities/{opportunity_id}/join", headers=headers(outsider)).status_code == 201
    engine.dispose()
