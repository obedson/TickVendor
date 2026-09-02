"""Leaderboard configuration API tests."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import Membership, MembershipRole
from src.security import create_access_token
from tests.test_database import create_event_context


def test_admin_can_configure_leaderboard_and_member_can_read(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'leaderboard-api.db'}", connect_args={"check_same_thread": False}); Base.metadata.create_all(engine); sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with Session(engine) as db:
        admin, community, _event = create_event_context(db); db.add(Membership(community_id=community.id, user_id=admin.id, role=MembershipRole.ADMIN)); db.commit(); ids = admin.id, community.id
    app = create_app()
    def override():
        with sessions() as db: yield db
    app.dependency_overrides[get_db] = override; client = TestClient(app); admin, community = ids; h = {"Authorization": f"Bearer {create_access_token(admin, 'participant')}"}
    response = client.post(f"/api/v1/admin/communities/{community}/leaderboards", headers=h, json={"name": "Overall", "slug": "overall-api", "metric": "overall", "period": "all_time", "max_entries": 20, "is_enabled": True})
    assert response.status_code in (200, 201), response.text
    assert client.get(f"/api/v1/leaderboards/{community}", headers=h).status_code == 200
    engine.dispose()
