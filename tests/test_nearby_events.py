"""Nearby event discovery tests."""
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import Community, Event, EventStatus, LocationType, Organization, User, Venue


def test_nearby_events_are_distance_filtered_and_sorted(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'nearby.db'}",connect_args={"check_same_thread":False});Base.metadata.create_all(engine);sessions=sessionmaker(bind=engine,expire_on_commit=False)
    with sessions() as db:
        user=User(email='nearby@example.com',password_hash='hash');db.add(user);db.flush();org=Organization(owner_id=user.id,name='Org',slug='nearby-org');db.add(org);db.flush();community=Community(organization_id=org.id,name='Community',slug='nearby-community');db.add(community);db.flush();now=datetime.now(UTC)
        near=Venue(name='Near',address='Near',latitude=Decimal('9.001'),longitude=Decimal('7.0'));far=Venue(name='Far',address='Far',latitude=Decimal('10.0'),longitude=Decimal('7.0'));db.add_all([near,far]);db.flush()
        common={'community_id':community.id,'organizer_id':user.id,'description':'Nearby event','category':'community','starts_at':now+timedelta(days=1),'ends_at':now+timedelta(days=2),'location_type':LocationType.PHYSICAL,'status':EventStatus.PUBLISHED}
        db.add_all([Event(**common,title='Near Event',slug='near-event',venue_id=near.id),Event(**common,title='Far Event',slug='far-event',venue_id=far.id)]);db.commit()
    app=create_app()
    def override_get_db():
        with sessions() as db:yield db
    app.dependency_overrides[get_db]=override_get_db;client=TestClient(app)
    response=client.get('/api/v1/events/nearby',params={'latitude':9.0,'longitude':7.0,'radius_km':5})
    assert response.status_code==200,response.text
    assert [item['title'] for item in response.json()]==['Near Event']
    assert response.json()[0]['distance_km']<1
    assert client.get('/api/v1/events/nearby',params={'latitude':91,'longitude':7}).status_code==422
    engine.dispose()
