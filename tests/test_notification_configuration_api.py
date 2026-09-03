"""Community notification-rule administration tests."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.database import get_db
from src.main import create_app
from src.models import AuditLog, NotificationRule
from tests.test_admin_configuration_product import headers, setup


def test_admin_can_configure_notification_rule_and_organizer_and_member_are_denied(tmp_path):
    engine, _client, (admin, member, community), sessions = setup(tmp_path)
    app = create_app()

    def override():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override
    client = TestClient(app)
    path = f"/api/v1/admin/communities/{community}/notification-rules"
    payload = {
        "notification_type": "event_reminder",
        "in_app_enabled": True,
        "email_enabled": True,
        "push_enabled": False,
        "is_active": True,
    }
    assert client.put(path, headers=headers(member), json=payload).status_code == 403
    saved = client.put(path, headers=headers(admin), json=payload)
    assert saved.status_code == 200
    assert saved.json()["notification_type"] == "event_reminder"
    assert client.get(path, headers=headers(admin)).json() == [saved.json()]
    assert client.get(path, headers=headers(member)).status_code == 403
    with sessions() as db:
        rule = db.query(NotificationRule).filter_by(community_id=community).one()
        assert rule.email_enabled is True and rule.push_enabled is False
        assert db.query(AuditLog).filter_by(action="notification_rule.updated", target_id=rule.id).count() == 1
    engine.dispose()
