"""Reversible policy enforcement without changing lifecycle/evidence."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from src.models import (
    ActivityOpportunity,
    AuditLog,
    Community,
    Event,
    EventStatus,
    LocationType,
    OpportunityStatus,
    Task,
    User,
)
from tests.test_community_management import headers, setup
from tests.test_governance_membership import platform


def content(sessions, community, admin):
    with sessions() as db:
        now = datetime.now(UTC)
        event = Event(community_id=community, organizer_id=admin, title='Policy Event', slug='policy-event',
            description='Event content', category='community', starts_at=now, ends_at=now+timedelta(days=1),
            location_type=LocationType.ONLINE, status=EventStatus.PUBLISHED)
        opportunity = ActivityOpportunity(community_id=community, created_by_id=admin, title='Policy Opportunity',
            description='Opportunity content', activity_type='service', dimension='service', starts_at=now,
            ends_at=now+timedelta(days=1), status=OpportunityStatus.PUBLISHED, members_only=False)
        task = Task(community_id=community, created_by_id=admin, title='Policy Task', description='Task content')
        db.add_all([event, opportunity, task]); db.commit()
        return event.id, opportunity.id, task.id


def test_content_moderation_enforces_discovery_direct_use_and_restore(tmp_path):
    engine, client, (admin, member, _, community), sessions = setup(tmp_path)
    super_id = platform(sessions)
    event, opportunity, task = content(sessions, community, admin)
    base = '/api/v1/admin/platform/governance'
    for kind, target in [('event', event), ('opportunity', opportunity), ('task', task)]:
        url = f'{base}/{kind}/{target}/moderation'
        assert client.post(url, headers=headers(admin), json={'suspended': True, 'reason':'Policy violation'}).status_code == 403
        assert client.post(url, headers=headers(super_id), json={'suspended':True, 'reason':'   '}).status_code == 422
        assert client.post(url, headers=headers(super_id), json={'suspended':True, 'reason':'Policy violation'}).status_code == 200
        assert client.post(url, headers=headers(super_id), json={'suspended':True, 'reason':'Duplicate action'}).status_code == 200
    assert client.get('/api/v1/events').json() == []
    assert client.get(f'/api/v1/events/{event}').status_code == 404
    assert client.post(f'/api/v1/events/{event}/publish', headers=headers(admin)).status_code == 403
    assert client.get(f'/api/v1/events/{event}/ticket-types', headers=headers(member)).status_code == 403
    attendance_root = f'/api/v1/events/{event}/attendance'
    assert client.post(attendance_root + '/check-in', headers=headers(member), json={}).status_code == 403
    assert client.post(attendance_root + '/qr-verify', headers=headers(admin), json={'attendance_id':str(uuid4()), 'ticket_id':str(uuid4())}).status_code == 403
    assert client.post(attendance_root + f'/{uuid4()}/organizer-review', headers=headers(admin), json={'approve':True, 'reason':'Cannot bypass moderation'}).status_code == 403
    assert client.get(attendance_root + '/roster', headers=headers(admin)).status_code == 200
    assert client.post(f'/api/v1/tasks/{task}/assignments', headers=headers(admin), json={'assignee_id':str(member)}).status_code == 403
    assert client.get('/api/v1/activity-opportunities', headers=headers(member)).json() == []
    assert client.post(f'/api/v1/activity-opportunities/{opportunity}/join', headers=headers(member)).status_code == 403
    assert client.get(f'/api/v1/communities/{community}/tasks', headers=headers(member)).json() == []
    search = client.get('/api/v1/search?q=Policy', headers=headers(member)).json()
    assert search['events'] == [] and search['tasks'] == []
    for kind, target in [('event',event),('opportunity',opportunity),('task',task)]:
        assert client.post(f'{base}/{kind}/{target}/moderation', headers=headers(super_id), json={'suspended':False,'reason':'Policy issue resolved'}).status_code == 200
    assert len(client.get('/api/v1/events').json()) == 1
    assert len(client.get('/api/v1/activity-opportunities', headers=headers(member)).json()) == 1
    with sessions() as db:
        assert db.get(Event,event).status == EventStatus.PUBLISHED
        assert db.get(ActivityOpportunity,opportunity).status == OpportunityStatus.PUBLISHED
        assert db.query(AuditLog).filter(AuditLog.action.like('moderation.%')).count() == 6
    history = client.get(base+'/history', headers=headers(super_id)).json()
    assert history and all(item['reason'] and item['actor'] and item['target_name'] and item['result'] for item in history)
    assert client.get(base+'/history', headers=headers(admin)).status_code == 403
    engine.dispose()


def test_user_and_community_suspension_are_reversible_and_retain_rows(tmp_path):
    engine, client, (admin, member, _, community), sessions = setup(tmp_path)
    super_id = platform(sessions)
    event, opportunity, _ = content(sessions, community, admin)
    base = '/api/v1/admin/platform/governance'
    assert client.post(f'{base}/user/{super_id}/moderation', headers=headers(super_id), json={'suspended':True,'reason':'Self lockout'}).status_code == 403
    assert client.post(f'{base}/user/{member}/moderation', headers=headers(super_id), json={'suspended':True,'reason':'Account policy issue'}).status_code == 200
    assert client.get('/api/v1/communities/me', headers=headers(member)).status_code == 401
    assert client.post(f'{base}/user/{member}/moderation', headers=headers(super_id), json={'suspended':False,'reason':'Account issue resolved'}).status_code == 200
    assert client.get('/api/v1/communities/me', headers=headers(member)).status_code == 200
    assert client.post(f'{base}/community/{community}/moderation', headers=headers(super_id), json={'suspended':True,'reason':'Community review'}).status_code == 200
    assert client.patch(f'/api/v1/communities/{community}', headers=headers(admin), json={'name':'Bypass suspension'}).status_code == 403
    assert client.get('/api/v1/events').json() == []
    assert client.get('/api/v1/activity-opportunities', headers=headers(member)).json() == []
    assert client.post(f'/api/v1/activity-opportunities/{opportunity}/join', headers=headers(member)).status_code == 403
    assert client.get(f'{base}/community/{community}', headers=headers(super_id)).status_code == 200
    assert client.post(f'{base}/community/{community}/moderation', headers=headers(super_id), json={'suspended':False,'reason':'Community cleared'}).status_code == 200
    with sessions() as db:
        assert db.get(User, member).is_active and db.get(Community,community).is_active
        assert db.get(Event,event).status == EventStatus.PUBLISHED
    assert client.get(base+'/user?q=member@example.com', headers=headers(super_id)).json()[0]['email'] == 'member@example.com'
    engine.dispose()
