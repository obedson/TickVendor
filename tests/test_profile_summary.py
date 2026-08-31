"""Complete member journey profile tests."""
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import ImpactTransaction, ImpactTransactionStatus, Membership, MembershipRole, Rank
from src.security import create_access_token
from tests.test_database import create_event_context


def test_member_profile_presents_dimensions_rank_and_next_rank_progress(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'profile-summary.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine); sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        user, community, _event = create_event_context(db)
        db.add(Membership(community_id=community.id, user_id=user.id, role=MembershipRole.MEMBER))
        db.add_all([
            Rank(community_id=community.id, name="Starter", slug="starter", minimum_points=0, sort_order=0),
            Rank(community_id=community.id, name="Active Member", slug="active", minimum_points=50, sort_order=1),
            ImpactTransaction(idempotency_key="profile-points", user_id=user.id, community_id=community.id,
                              points=20, source_type="test", reason="Profile test",
                              status=ImpactTransactionStatus.POSTED),
        ]); db.commit(); user_id, community_id = user.id, community.id
    app = create_app()
    def override_get_db():
        with sessions() as db: yield db
    app.dependency_overrides[get_db] = override_get_db
    headers = {"Authorization": f"Bearer {create_access_token(user_id, 'participant')}"}
    response = TestClient(app).get('/api/v1/profiles/me', params={'community_id': str(community_id)}, headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['rank']['name'] == 'Starter'
    assert data['next_rank']['name'] == 'Active Member'
    assert data['next_rank']['points_remaining'] == 30
    assert data['engagement_dimensions'] == {'participation': 0, 'execution': 0, 'contribution': 0, 'service': 0, 'leadership': 0}
    assert data['achievement_timeline'][0]['type'] == 'joined_community'
    engine.dispose()


def test_member_profile_denies_cross_community_summary(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'profile-denial.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine); sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        user, community, _event = create_event_context(db); db.commit(); user_id, community_id = user.id, community.id
    app = create_app()
    def override_get_db():
        with sessions() as db: yield db
    app.dependency_overrides[get_db] = override_get_db
    response = TestClient(app).get('/api/v1/profiles/me', params={'community_id': str(community_id)}, headers={"Authorization": f"Bearer {create_access_token(user_id, 'participant')}"})
    assert response.status_code == 403
    engine.dispose()
