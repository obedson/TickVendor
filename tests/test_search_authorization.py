"""Global search authorization tests."""
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import Community, Membership, MembershipRole, Organization, Profile, Task, User
from src.security import create_access_token


def test_search_returns_organizers_and_only_authorized_tasks(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'search.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        organizer = User(email="organizer@example.com", password_hash="hash")
        organizer.profile = Profile(username="grace-organizer", display_name="Grace Organizer")
        member = User(email="member@example.com", password_hash="hash")
        member.profile = Profile(username="member", display_name="Member")
        outsider = User(email="outsider@example.com", password_hash="hash")
        outsider.profile = Profile(username="outsider", display_name="Outsider")
        db.add_all([organizer, member, outsider]); db.flush()
        organization = Organization(owner_id=organizer.id, name="Org", slug="search-org")
        db.add(organization); db.flush()
        community = Community(organization_id=organization.id, name="Search Community", slug="search-community")
        db.add(community); db.flush()
        db.add_all([
            Membership(community_id=community.id, user_id=organizer.id, role=MembershipRole.ORGANIZER),
            Membership(community_id=community.id, user_id=member.id),
            Task(community_id=community.id, created_by_id=organizer.id, title="Welcome desk", description="Greet guests"),
        ])
        db.commit(); member_id, outsider_id = member.id, outsider.id
    app = create_app()
    def override_get_db():
        with sessions() as db: yield db
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    headers = lambda user_id: {"Authorization": f"Bearer {create_access_token(user_id, 'participant')}"}
    organizer_result = client.get('/api/v1/search', params={'q': 'Grace'}, headers=headers(outsider_id))
    assert organizer_result.json()['organizers'][0]['username'] == 'grace-organizer'
    member_result = client.get('/api/v1/search', params={'q': 'Welcome'}, headers=headers(member_id))
    assert member_result.json()['tasks'][0]['title'] == 'Welcome desk'
    outsider_result = client.get('/api/v1/search', params={'q': 'Welcome'}, headers=headers(outsider_id))
    assert outsider_result.json()['tasks'] == []
    community_result = client.get(
        f'/api/v1/communities/{community.id}',
        headers=headers(member_id),
    )
    assert community_result.status_code == 200, community_result.text
    assert community_result.json() == {
        'id': str(community.id),
        'name': 'Search Community',
        'slug': 'search-community',
        'logo_url': None,
        'description': None,
        'counts': {
            'members': 2,
            'administrators': 1,
            'events': 0,
            'tasks': 1,
            'activities': 0,
            'contributions': 0,
            'ranks': 0,
            'badges': 0,
            'milestones': 0,
        },
    }
    outsider_community = client.get(
        f'/api/v1/communities/{community.id}',
        headers=headers(outsider_id),
    )
    assert outsider_community.status_code == 403
    engine.dispose()
