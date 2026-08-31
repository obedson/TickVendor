"""Administration API tests for configurable recognition definitions."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import Community, Membership, MembershipRole, Organization, User
from src.security import create_access_token


def test_community_admin_can_create_milestone_and_outsider_cannot(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'admin-config.db'}",
        connect_args={"check_same_thread": False},
    )
    event.listen(engine, "connect", lambda conn, _record: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        admin = User(email="config-admin@example.com", password_hash="hash")
        outsider = User(email="config-outsider@example.com", password_hash="hash")
        db.add_all([admin, outsider])
        db.flush()
        organization = Organization(owner_id=admin.id, name="Org", slug="config-org")
        db.add(organization)
        db.flush()
        community = Community(
            organization_id=organization.id,
            name="Community",
            slug="config-community",
        )
        db.add(community)
        db.flush()
        db.add(
            Membership(
                community_id=community.id,
                user_id=admin.id,
                role=MembershipRole.ADMIN,
            )
        )
        db.commit()
        ids = admin.id, outsider.id, community.id

    app = create_app()

    def override_get_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    admin_id, outsider_id, community_id = ids
    payload = {
        "name": "Community Builder",
        "slug": "community-builder",
        "description": "Recognizes sustained engagement",
        "reward_points": 25,
        "requirements": [
            {"metric": "impact_points", "operator": ">=", "threshold": 300},
            {"metric": "attendance_count", "operator": ">=", "threshold": 10},
        ],
    }
    denied = client.post(
        f"/api/v1/admin/communities/{community_id}/milestones",
        json=payload,
        headers={"Authorization": f"Bearer {create_access_token(outsider_id, 'participant')}"},
    )
    assert denied.status_code == 403
    created = client.post(
        f"/api/v1/admin/communities/{community_id}/milestones",
        json=payload,
        headers={"Authorization": f"Bearer {create_access_token(admin_id, 'participant')}"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["slug"] == "community-builder"
    engine.dispose()
