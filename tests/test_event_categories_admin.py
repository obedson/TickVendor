"""Event category administration API tests."""
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import EventCategory, PlatformRole, User
from src.security import create_access_token


def test_super_admin_can_add_and_edit_categories(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'categories.db'}",connect_args={"check_same_thread":False})
    Base.metadata.create_all(engine);sessions=sessionmaker(bind=engine,expire_on_commit=False)
    with sessions() as db:
        admin=User(email='admin@example.com',password_hash='hash',role=PlatformRole.SUPER_ADMIN)
        participant=User(email='user@example.com',password_hash='hash')
        db.add_all([admin,participant]);db.commit();admin_id,participant_id=admin.id,participant.id
    app=create_app()
    def override_get_db():
        with sessions() as db:yield db
    app.dependency_overrides[get_db]=override_get_db;client=TestClient(app)
    denied=client.post('/api/v1/admin/categories',json={'slug':'health','name':'Health'},headers={'Authorization':f"Bearer {create_access_token(participant_id,'participant')}"})
    assert denied.status_code==403
    created=client.post('/api/v1/admin/categories',json={'slug':'health','name':'Health'},headers={'Authorization':f"Bearer {create_access_token(admin_id,'super_admin')}"})
    assert created.status_code==201,created.text;category_id=created.json()['id']
    updated=client.patch(f'/api/v1/admin/categories/{category_id}',json={'name':'Health and Wellness','is_active':False},headers={'Authorization':f"Bearer {create_access_token(admin_id,'super_admin')}"})
    assert updated.status_code==200,updated.text
    with sessions() as db:
        category=db.get(EventCategory,category_id);assert category.name=='Health and Wellness';assert category.is_active is False
    engine.dispose()
