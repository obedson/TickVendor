"""Membership state machine, scoped authority and escalation regressions."""
from uuid import UUID

from src.models import (
    AuditLog,
    Community,
    Membership,
    MembershipAccess,
    MembershipRole,
    Notification,
    PlatformRole,
    User,
)
from tests.test_community_management import headers, setup


def platform(sessions):
    with sessions() as db:
        user = User(email="super@example.com", password_hash="unused-test-hash", role=PlatformRole.SUPER_ADMIN)
        db.add(user); db.commit()
        return user.id


def set_access(sessions, community_id, mode):
    with sessions() as db:
        db.get(Community, community_id).membership_access = mode
        db.commit()


def test_open_join_leave_rejoin_and_isolated_history(tmp_path):
    engine, client, (admin, _, outsider, community), sessions = setup(tmp_path)
    set_access(sessions, community, MembershipAccess.OPEN)
    url = f"/api/v1/communities/{community}/membership"
    joined = client.post(url + "/join", headers=headers(outsider))
    assert joined.status_code == 200 and joined.json()["role"] == "member"
    assert client.post(url + "/join", headers=headers(outsider)).json() == joined.json()
    assert client.post(url + "/leave", headers=headers(outsider)).json()["status"] == "left"
    assert client.post(url + "/accept", headers=headers(outsider)).status_code == 409
    assert client.post(url + "/join", headers=headers(outsider)).json()["id"] == joined.json()["id"]
    assert client.post(url + "/leave", headers=headers(admin)).status_code == 409
    with sessions() as db:
        assert db.query(Membership).filter_by(user_id=outsider, community_id=community).count() == 1
        assert db.query(AuditLog).filter_by(target_id=UUID(joined.json()["id"])).count() == 3
    engine.dispose()


def test_approval_rejection_withdrawal_and_invalid_activation(tmp_path):
    engine, client, (admin, _, outsider, community), sessions = setup(tmp_path)
    set_access(sessions, community, MembershipAccess.APPROVAL_REQUIRED)
    root = f"/api/v1/communities/{community}"
    pending = client.post(root + "/membership/join", headers=headers(outsider)).json()
    assert pending["status"] == "pending"
    assert client.patch(root + f"/members/{pending['id']}/status", headers=headers(admin), json={"status": "active", "reason": "Cannot bypass review"}).status_code == 409
    assert client.post(root + "/membership/withdraw", headers=headers(outsider)).json()["status"] == "left"
    client.post(root + "/membership/join", headers=headers(outsider))
    review = root + f"/membership-requests/{pending['id']}"
    assert client.post(review + "/approved", headers=headers(outsider), json={"reason": "Not authorized"}).status_code == 403
    assert client.post(review + "/rejected", headers=headers(admin), json={"reason": "Does not meet requirements"}).json()["status"] == "declined"
    client.post(root + "/membership/join", headers=headers(outsider))
    assert client.post(review + "/approved", headers=headers(admin), json={"reason": "Requirements met"}).json()["status"] == "active"
    assert client.post(review + "/approved", headers=headers(admin), json={"reason": "Repeated approval"}).status_code == 200
    with sessions() as db:
        assert db.query(Notification).filter_by(user_id=outsider, notification_type="membership_approved").count() == 1
    engine.dispose()


def test_invite_accept_decline_reinvite_and_private_discovery(tmp_path):
    engine, client, (admin, _, outsider, community), sessions = setup(tmp_path)
    root = f"/api/v1/communities/{community}"
    with sessions() as db:
        db.get(Community, community).is_public = False; db.commit()
    assert client.get('/api/v1/communities/discover', headers=headers(outsider)).json() == []
    assert client.post(root + '/membership/join', headers=headers(outsider)).status_code == 404
    payload = {"identifier": "outsider@example.com", "role": "organizer"}
    invited = client.post(root + '/members/invite', headers=headers(admin), json=payload)
    assert invited.status_code == 201
    assert client.post(root + '/members/invite', headers=headers(admin), json=payload).json()['id'] == invited.json()['id']
    assert client.get('/api/v1/communities/me', headers=headers(outsider)).json()[0]['membership']['status'] == 'invited'
    assert client.post(root + '/membership/decline', headers=headers(outsider)).json()['status'] == 'declined'
    assert client.post(root + '/members/invite', headers=headers(admin), json=payload).status_code == 201
    assert client.post(root + '/membership/accept', headers=headers(outsider)).json()['role'] == 'organizer'
    assert client.post(root + '/membership/accept', headers=headers(outsider)).status_code == 200
    engine.dispose()


def test_super_admin_only_grants_and_removes_administrator_authority(tmp_path):
    engine, client, (admin, member, outsider, community), sessions = setup(tmp_path)
    super_id = platform(sessions)
    root = f'/api/v1/admin/platform/governance/community/{community}'
    payload = {'user_id': str(outsider), 'reason': 'Appointed community administrator'}
    assert client.post(root + '/administrators', headers=headers(admin), json=payload).status_code == 403
    assigned = client.post(root + '/administrators', headers=headers(super_id), json=payload)
    assert assigned.status_code == 200, assigned.text
    item_id = assigned.json()['id']
    normal = f'/api/v1/communities/{community}/members/{item_id}'
    legacy = f'/api/v1/admin/communities/{community}/memberships/{item_id}/role'
    assert client.patch(legacy, headers=headers(admin), json={'role': 'member', 'reason': 'Legacy demotion bypass'}).status_code == 403
    assert client.patch(normal + '/role', headers=headers(admin), json={'role': 'member', 'reason': 'Attempted demotion'}).status_code == 403
    assert client.patch(normal + '/status', headers=headers(admin), json={'status': 'suspended', 'reason': 'Attempted removal'}).status_code == 403
    assert client.patch(normal + '/role', headers=headers(outsider), json={'role': 'member', 'reason': 'Own role change'}).status_code == 403
    assert client.patch(root + f'/memberships/{item_id}', headers=headers(super_id), json={'action': 'role_changed', 'role': 'organizer', 'reason': 'Reassigned responsibility'}).json()['role'] == 'organizer'
    assert client.post('/api/v1/communities', headers=headers(member), json={'name': 'Privilege escalation', 'slug': 'escalation'}).status_code == 403
    with sessions() as db:
        membership = db.query(Membership).filter_by(user_id=member, community_id=community).one()
        target = str(membership.id)
        other = Community(organization_id=db.get(Community, community).organization_id, name='Other', slug='other', is_public=False)
        db.add(other); db.flush(); other_id = other.id
        db.add(Membership(community_id=other.id, user_id=outsider, role=MembershipRole.ADMIN)); db.commit()
    assert client.patch(f'/api/v1/communities/{other_id}/members/{target}/role', headers=headers(admin), json={'role':'organizer','reason':'Cross tenant'}).status_code == 403
    assert client.patch(f'/api/v1/communities/{community}/members/{target}/role', headers=headers(admin), json={'role':'admin','reason':'Unauthorized promotion'}).status_code == 403
    assert client.patch(f'/api/v1/admin/communities/{community}/memberships/{target}/role', headers=headers(admin), json={'role':'admin','reason':'Legacy escalation bypass'}).status_code == 403
    engine.dispose()


def test_suspended_members_cannot_self_rejoin_or_bypass_review(tmp_path):
    engine, client, (admin, member, _, community), sessions = setup(tmp_path)
    set_access(sessions, community, MembershipAccess.OPEN)
    with sessions() as db:
        membership = db.query(Membership).filter_by(user_id=member, community_id=community).one()
        mid = membership.id
    root = f'/api/v1/communities/{community}'
    assert client.patch(root + f'/members/{mid}/status', headers=headers(admin), json={'status':'suspended','reason':'Membership policy violation'}).status_code == 200
    assert client.post(root + '/membership/join', headers=headers(member)).status_code == 409
    assert client.post(root + '/membership/accept', headers=headers(member)).status_code == 409
    assert client.patch(root + f'/members/{mid}/status', headers=headers(admin), json={'status':'active','reason':'Issue resolved'}).status_code == 200
    engine.dispose()


def test_final_admin_is_super_admin_governed_and_creation_never_self_grants(tmp_path):
    engine, client, (admin, _, _, community), sessions = setup(tmp_path)
    super_id = platform(sessions)
    with sessions() as db:
        admin_membership = db.query(Membership).filter_by(user_id=admin, community_id=community).one().id
    root = f'/api/v1/admin/platform/governance/community/{community}'
    assert client.get(root, headers=headers(super_id)).json()['active_admin_count'] == 1
    response = client.patch(root + f'/memberships/{admin_membership}', headers=headers(super_id),
                            json={'action':'role_changed','role':'organizer','reason':'Platform assumes governance pending reassignment'})
    assert response.status_code == 200
    assert client.get(root, headers=headers(super_id)).json()['active_admin_count'] == 0
    assert client.post(root + '/administrators', headers=headers(super_id),
                       json={'user_id':str(admin),'reason':'Restore local administrator'}).status_code == 200
    created = client.post('/api/v1/communities', headers=headers(admin), json={'name':'New governed community','slug':'new-governed'})
    assert created.status_code == 201
    with sessions() as db:
        own = db.query(Membership).filter_by(user_id=admin, community_id=UUID(created.json()['id'])).one()
        assert own.role == MembershipRole.ORGANIZER
    engine.dispose()
