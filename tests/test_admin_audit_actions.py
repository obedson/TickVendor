"""Administrative audit coverage for revocations, ranks, and role changes."""
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import (
    AuditLog,
    Badge,
    BadgeAward,
    Community,
    Membership,
    MembershipRole,
    Organization,
    Rank,
    User,
)
from src.security import create_access_token


def test_admin_changes_are_audited_and_outsiders_are_denied(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'admin-audit.db'}",connect_args={"check_same_thread":False});Base.metadata.create_all(engine);sessions=sessionmaker(bind=engine,expire_on_commit=False)
    with sessions() as db:
        admin=User(email='admin@example.com',password_hash='hash');member=User(email='member@example.com',password_hash='hash');outsider=User(email='outsider@example.com',password_hash='hash');db.add_all([admin,member,outsider]);db.flush()
        org=Organization(owner_id=admin.id,name='Org',slug='audit-org');db.add(org);db.flush();community=Community(organization_id=org.id,name='Community',slug='audit-community');db.add(community);db.flush()
        admin_membership=Membership(community_id=community.id,user_id=admin.id,role=MembershipRole.ADMIN);member_membership=Membership(community_id=community.id,user_id=member.id);rank=Rank(community_id=community.id,name='Member',slug='member',minimum_points=0,sort_order=0);badge=Badge(community_id=community.id,name='Badge',slug='badge',category='service');db.add_all([admin_membership,member_membership,rank,badge]);db.flush();award=BadgeAward(badge_id=badge.id,user_id=member.id,idempotency_key='award-key',awarded_at=datetime.now(UTC));db.add(award);db.commit();ids=admin.id,outsider.id,community.id,member_membership.id,rank.id,award.id
    app=create_app()
    def override_get_db():
        with sessions() as db:yield db
    app.dependency_overrides[get_db]=override_get_db;client=TestClient(app);admin_id,outsider_id,community_id,membership_id,rank_id,award_id=ids
    headers=lambda uid:{'Authorization':f"Bearer {create_access_token(uid,'participant')}"}
    path=f'/api/v1/admin/communities/{community_id}'
    assert client.patch(f'{path}/memberships/{membership_id}/role',json={'role':'organizer','reason':'Assign responsibility'},headers=headers(outsider_id)).status_code==403
    assert client.patch(f'{path}/memberships/{membership_id}/role',json={'role':'organizer','reason':'Assign responsibility'},headers=headers(admin_id)).status_code==200
    assert client.patch(f'{path}/ranks/{rank_id}',json={'minimum_points':25},headers=headers(admin_id)).status_code==200
    assert client.post(f'{path}/badge-awards/{award_id}/revoke',json={'reason':'Awarded in error'},headers=headers(admin_id)).status_code==204
    with sessions() as db:assert {row.action for row in db.query(AuditLog)} >= {'membership.role_changed','rank.changed','badge.revoked'}
    engine.dispose()
