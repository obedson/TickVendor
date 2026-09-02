"""Participant community context API tests."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import Membership, MembershipRole, MembershipStatus
from src.security import create_access_token
from tests.test_database import create_event_context


def test_member_can_list_active_communities_without_leaking_other_tenants(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'my-communities.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        user, community, _event = create_event_context(db)
        from src.models import Community, Event, Organization, PlatformRole, Profile, User
        other_user = User(email="other-owner@example.com", password_hash="hashed", role=PlatformRole.PARTICIPANT,
                          profile=Profile(username="other-owner", display_name="Other Owner"))
        db.add(other_user); db.flush()
        organization = Organization(owner_id=other_user.id, name="Other Org", slug="other-org")
        db.add(organization); db.flush()
        other_community = Community(organization_id=organization.id, name="Other Community", slug="other-community")
        db.add(other_community); db.flush()
        db.add(Event(community_id=other_community.id, organizer_id=other_user.id, title="Other Event", slug="other-event",
                     description="Other", category="other", starts_at=datetime.now(UTC), ends_at=datetime.now(UTC),
                     location_type="online"))
        db.add(Membership(community_id=community.id, user_id=user.id, role=MembershipRole.MEMBER, status=MembershipStatus.ACTIVE))
        db.add(Membership(community_id=other_community.id, user_id=user.id, role=MembershipRole.MEMBER, status=MembershipStatus.INVITED))
        db.commit()
        user_id = user.id
    app = create_app()
    def override():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = override
    response = TestClient(app).get(
        "/api/v1/communities/me",
        headers={"Authorization": f"Bearer {create_access_token(user_id, 'participant')}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body] == [str(community.id)]
    assert body[0]["membership"]["role"] == "member"
    engine.dispose()
