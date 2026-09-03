"""Cross-tenant recognition reference validation tests."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.database import get_db
from src.main import create_app
from src.models import Badge, Community, Organization, Rank
from tests.test_admin_configuration_product import headers, setup


def test_rank_rejects_cross_community_badge_requirement(tmp_path):
    engine, _client, (admin, _member, community), sessions = setup(tmp_path)
    with sessions() as db:
        other_org = Organization(owner_id=admin, name="Referenced Org", slug="referenced-org")
        db.add(other_org)
        db.flush()
        other = Community(
            organization_id=other_org.id,
            name="Referenced Community",
            slug="referenced-community",
        )
        db.add(other)
        db.flush()
        badge = Badge(
            community_id=other.id,
            name="Other Badge",
            slug="other-badge",
            category="test",
            requirements={},
        )
        db.add(badge)
        db.commit()
        badge_id = badge.id

    app = create_app()

    def override():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override
    client = TestClient(app)
    response = client.post(
        f"/api/v1/admin/communities/{community}/ranks",
        headers=headers(admin),
        json={
            "name": "Invalid Rank",
            "slug": "invalid-rank",
            "minimum_points": 0,
            "sort_order": 1,
            "requirements": [
                {"requirement_type": "badge", "reference_id": str(badge_id), "threshold": 1}
            ],
        },
    )

    assert response.status_code == 422
    with sessions() as db:
        assert db.query(Rank).filter_by(community_id=community).count() == 0
    engine.dispose()
