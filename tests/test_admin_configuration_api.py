"""Administration API tests for configurable recognition definitions."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import (
    AchievementRule,
    Badge,
    Community,
    Membership,
    MembershipRole,
    Milestone,
    Organization,
    Rank,
    User,
)
from src.security import create_access_token
from tests.test_admin_configuration_product import headers, setup


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

    with sessions() as db:
        streak = AchievementRule(
            community_id=community_id,
            name="Four Week Activity Streak",
            slug="four-week-activity-streak",
            condition_tree={
                "operator": ">=",
                "metric": "consecutive_activities",
                "value": 4,
            },
            reward_definition={},
            is_active=False,
        )
        db.add(streak)
        db.commit()
        streak_id = streak.id

    toggled = client.patch(
        f"/api/v1/admin/communities/{community_id}/achievement-rules/{streak_id}",
        json={"is_active": True},
        headers={"Authorization": f"Bearer {create_access_token(admin_id, 'participant')}"},
    )
    assert toggled.status_code == 200, toggled.text
    assert toggled.json()["is_active"] is True
    engine.dispose()


def test_recognition_lists_are_tenant_scoped_and_role_protected(tmp_path):
    engine, client, (admin, member, community), sessions = setup(tmp_path)
    with sessions() as db:
        db.add_all([
            AchievementRule(community_id=community, name="Rule", slug="rule", condition_tree={}, reward_definition={}),
            Badge(community_id=community, name="Badge", slug="badge", category="test", requirements={}),
            Milestone(community_id=community, name="Milestone", slug="milestone"),
            Rank(community_id=community, name="Rank", slug="rank", minimum_points=10, sort_order=1),
        ])
        db.commit()
    for resource, expected in [("achievement-rules", "Rule"), ("badges", "Badge"), ("milestones", "Milestone"), ("ranks", "Rank")]:
        response = client.get(f"/api/v1/admin/communities/{community}/{resource}", headers=headers(admin))
        assert response.status_code == 200
        assert [item["name"] for item in response.json()] == [expected]
        assert client.get(f"/api/v1/admin/communities/{community}/{resource}", headers=headers(member)).status_code == 403
    engine.dispose()


def test_recognition_mutations_allow_community_admin_and_deny_member_and_cross_community(tmp_path):
    engine, client, (admin, member, community), sessions = setup(tmp_path)
    with sessions() as db:
        db.query(Membership).filter_by(community_id=community, user_id=member).one().role = MembershipRole.ORGANIZER
        participant = User(email="recognition-participant@example.com", password_hash="hash")
        db.add(participant); db.flush()
        db.add(Membership(community_id=community, user_id=participant.id, role=MembershipRole.MEMBER))
        other_org = Organization(owner_id=admin, name="Other Org", slug="other-org")
        db.add(other_org); db.flush()
        other = Community(organization_id=other_org.id, name="Other", slug="other-community")
        db.add(other); db.commit(); other_id, participant_id = other.id, participant.id
    payloads = {
        "achievement-rules": {"name": "Rule", "slug": "rule", "condition_tree": {"metric": "impact_points", "operator": ">=", "value": 1}, "reward_definition": {}},
        "badges": {"name": "Badge", "slug": "badge", "category": "test", "requirements": {"metric": "attendance_count", "operator": ">=", "value": 1}, "reward_points": 0},
        "milestones": {"name": "Milestone", "slug": "milestone", "requirements": [{"metric": "attendance_count", "operator": ">=", "threshold": 1}]},
        "ranks": {"name": "Rank", "slug": "rank", "minimum_points": 10, "sort_order": 1, "requirements": [{"requirement_type": "attendance_count", "threshold": 1}]},
    }
    with sessions() as db:
        db.commit()
    for resource, payload in payloads.items():
        assert client.post(f"/api/v1/admin/communities/{community}/{resource}", headers=headers(admin), json=payload).status_code == 201
        assert client.post(f"/api/v1/admin/communities/{community}/{resource}", headers=headers(member), json={**payload, "slug": f"member-{payload['slug']}"}).status_code == 403
        assert client.get(f"/api/v1/admin/communities/{community}/{resource}", headers=headers(member)).status_code == 403
        assert client.post(f"/api/v1/admin/communities/{community}/{resource}", headers=headers(participant_id), json={**payload, "slug": f"participant-{payload['slug']}"}).status_code == 403
        assert client.post(f"/api/v1/admin/communities/{other_id}/{resource}", headers=headers(member), json={**payload, "slug": f"other-{payload['slug']}"}).status_code == 403
    engine.dispose()
