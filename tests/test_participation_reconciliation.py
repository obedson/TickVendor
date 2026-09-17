"""Focused end-to-end API/domain checks, with disposable local persistence."""
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from src.models import (
    Community,
    ImpactTransaction,
    Membership,
    MembershipStatus,
    PlatformRole,
    ScheduledNotification,
    TaskAttachment,
    TaskSubmission,
    User,
)
from tests.test_community_management import headers
from tests.test_task_staging_reconciliation import context as original_context
from tests.test_task_staging_reconciliation import create_assigned, quiz


@pytest.fixture(name="context")
def participation_context(tmp_path):
    yield from original_context.__wrapped__(tmp_path)


def test_bulk_resolution_scopes_email_and_deduplicates(context):
    client, (admin, member, outsider, _), sessions = context
    task, _ = create_assigned(context)
    path = f'/api/v1/tasks/{task}'
    response = client.post(path + '/assignment-candidates', headers=headers(admin), json={'emails': ' MEMBER@example.com, member@example.com; outsider@example.com\nwrong-address'})
    assert response.status_code == 200, response.text
    assert response.json()['count'] == 1
    assert response.json()['members'][0]['user_id'] == str(member)
    assert response.json()['unresolved'] == ['outsider@example.com']
    assert response.json()['invalid'] == ['wrong-address']
    assert client.post(path + '/assignment-candidates', headers=headers(member), json={}).status_code == 403
    assert client.post(path + '/assignments/bulk', headers=headers(admin), json={'selected_ids': [str(outsider)]}).status_code == 422
    preview = client.post(path + '/assignment-candidates', headers=headers(admin), json={'all_members': True}).json()
    payload = {'all_members': True, 'selection_version': preview['selection_version']}
    result = client.post(path + '/assignments/bulk', headers=headers(admin), json=payload)
    assert result.status_code == 200, result.text
    assert result.json() == {'assigned': 1, 'already_assigned': 1}
    assert client.post(path + '/assignments/bulk', headers=headers(admin), json=payload).json()['assigned'] == 0
    with sessions() as db:
        assert db.query(ScheduledNotification).filter_by(notification_type='task_assigned').count() == 1
        db.get(User, member).is_active = False; db.commit()
    assert client.post(path + '/assignments/bulk', headers=headers(admin), json=payload).status_code == 409


def test_bulk_selected_members_rechecked(context):
    client, (admin, member, _, community), sessions = context
    task, _ = create_assigned(context)
    with sessions() as db:
        membership = db.scalar(select(Membership).where(Membership.user_id == member, Membership.community_id == community))
        membership.status = MembershipStatus.SUSPENDED; db.commit()
    result = client.post(f'/api/v1/tasks/{task}/assignments/bulk', headers=headers(admin), json={'selected_ids': [str(member)]})
    assert result.status_code == 422


def test_member_directory_scopes_email_to_community_managers(context):
    """Managers must tell similar display names apart; ordinary members must not harvest emails."""
    client, (admin, member, outsider, community), _ = context
    path = f'/api/v1/communities/{community}/members'
    managed = client.get(path, headers=headers(admin))
    assert managed.status_code == 200, managed.text
    rows = {row['user_id']: row for row in managed.json()['members']}
    assert rows[str(member)]['display_name'] == 'Member'
    assert rows[str(member)]['email'] == 'member@example.com'
    plain = client.get(path, headers=headers(member))
    assert plain.status_code == 200, plain.text
    assert sorted(row['display_name'] for row in plain.json()['members']) == ['Admin', 'Member']
    assert all('email' not in row for row in plain.json()['members'])
    # Tenant boundary is server-side: a non-member never reaches the directory at all.
    assert client.get(path, headers=headers(outsider)).status_code == 403


def test_member_directory_email_boundary_covers_organizers_and_suspended_memberships(context):
    """Organizers run the assignment and roster workflows that need member emails; a suspended membership loses the directory entirely."""
    from src.models import MembershipRole
    client, (admin, member, _, community), sessions = context
    path = f'/api/v1/communities/{community}/members'
    with sessions() as db:
        item = db.scalar(select(Membership).where(Membership.user_id == member, Membership.community_id == community))
        item.role = MembershipRole.ORGANIZER; db.commit()
    rows = {row['user_id']: row for row in client.get(path, headers=headers(member)).json()['members']}
    assert rows[str(admin)]['email'] == 'admin@example.com'
    with sessions() as db:
        item = db.scalar(select(Membership).where(Membership.user_id == member, Membership.community_id == community))
        item.status = MembershipStatus.SUSPENDED; db.commit()
    assert client.get(path, headers=headers(member)).status_code == 403


def test_private_upload_and_authorized_retrieval(context, monkeypatch):
    client, (admin, member, outsider, _), sessions = context
    task, assignment = create_assigned(context, required_evidence_types=['attachment'])
    class Storage:
        def __init__(self): self.data = {}
        def put(self, key, data, content_type): self.data[key] = data
        def delete(self, key): self.data.pop(key, None)
        def get_url(self, key): return 'https://signed.example.test/temporary?signature=test'
    storage = Storage()
    monkeypatch.setattr('src.api.task_evidence.get_object_storage', lambda: storage)
    path = f'/api/v1/task-assignments/{assignment}/attachments'
    files = {'upload': ('../../proof.pdf', b'%PDF-1.7\nTest evidence', 'application/pdf')}
    assert client.post(path, headers=headers(outsider), files=files).status_code == 404
    assert client.post(path, headers=headers(member), files={'upload': ('bad.pdf', b'html', 'application/pdf')}).status_code == 422
    assert client.post(path, headers=headers(member), files={'upload': ('large.pdf', b'%PDF-' + b'x' * (5 * 1024 * 1024), 'application/pdf')}).status_code == 413
    response = client.post(path, headers=headers(member), files=files)
    assert response.status_code == 201, response.text
    attachment = response.json()['id']
    assert response.json()['filename'] == 'proof.pdf' and 'object_key' not in response.text
    assert client.post(path, headers=headers(member), files=files).json()['id'] == attachment
    for actor in (member, admin):
        response = client.get(f'/api/v1/task-attachments/{attachment}', headers=headers(actor))
        assert response.status_code == 200 and 'no-store' in response.headers['cache-control']
    assert client.get(f'/api/v1/task-attachments/{attachment}', headers=headers(outsider)).status_code == 403
    payload = {'attachment_ids': [attachment], 'idempotency_key': str(uuid4()),
               'evidence_url': 'https://legacy.example.test/proof',
               'evidence_attachments': ['https://legacy.example.test/one', 'https://legacy.example.test/two']}
    submitted = client.post(f'/api/v1/task-assignments/{assignment}/submissions', headers=headers(member), json=payload)
    assert submitted.status_code == 201, submitted.text
    assert client.post(f'/api/v1/task-assignments/{assignment}/submissions', headers=headers(member), json=payload).json()['id'] == submitted.json()['id']
    with sessions() as db:
        assert db.query(TaskAttachment).count() == 1
        record = db.query(TaskSubmission).one()
        assert record.attachment_ids == [attachment]
        assert record.evidence_url == 'https://legacy.example.test/proof'
        assert record.evidence_attachments == ['https://legacy.example.test/one', 'https://legacy.example.test/two']
    # Authorized history must expose legacy links *beside* private attachment ids, not instead of them.
    detail = client.get(f'/api/v1/tasks/{task}', headers=headers(member))
    history = detail.json()['history'][0]
    assert history['attachment_ids'] == [attachment]
    assert history['evidence_url'] == 'https://legacy.example.test/proof'
    assert history['evidence_attachments'] == ['https://legacy.example.test/one', 'https://legacy.example.test/two']
    queue = client.get(f'/api/v1/communities/{context[1][3]}/task-verification-queue', headers=headers(admin)).json()[0]
    assert queue['attachment_ids'] == [attachment]
    assert queue['evidence_url'] == 'https://legacy.example.test/proof'
    assert queue['evidence_attachments'] == ['https://legacy.example.test/one', 'https://legacy.example.test/two']


def test_attachment_cannot_be_borrowed_between_assignments(context, monkeypatch):
    client, (_, member, _, _), sessions = context
    _, first = create_assigned(context)
    _, second = create_assigned(context)
    with sessions() as db:
        item = TaskAttachment(assignment_id=UUID(first), owner_id=member, object_key='private/test', filename='proof.pdf', content_type='application/pdf', size_bytes=12, sha256='0'*64)
        db.add(item); db.commit(); attachment = str(item.id)
    response = client.post(f'/api/v1/task-assignments/{second}/submissions', headers=headers(member), json={'attachment_ids': [attachment]})
    assert response.status_code == 422


@pytest.mark.parametrize('failure', ['missing', 'outside', 'stale', 'inaccurate'])
def test_task_gps_required_is_server_enforced(context, failure):
    client, (_, member, _, _), sessions = context
    config = {'geofence': {'required': True, 'latitude': 6.5, 'longitude': 3.3, 'radius_meters': 100}}
    _, assignment = create_assigned(context, task_type='physical', task_config=config, verification_required=False)
    point = {'latitude': 6.5, 'longitude': 3.3, 'accuracy_meters': 10, 'captured_at': datetime.now(UTC).isoformat()}
    if failure == 'outside': point['latitude'] = 7
    if failure == 'stale': point['captured_at'] = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    if failure == 'inaccurate': point['accuracy_meters'] = 200
    response = client.post(f'/api/v1/task-assignments/{assignment}/submissions', headers=headers(member), json={} if failure == 'missing' else {'location': point})
    assert response.status_code == 422, response.text
    with sessions() as db:
        assert db.query(TaskSubmission).count() == db.query(ImpactTransaction).count() == 0


def test_task_gps_success_preserves_review_and_awards_once(context):
    client, (admin, member, _, _), sessions = context
    _task, assignment = create_assigned(context, task_type='physical', task_config={'geofence': {'required': True, 'latitude': 6.5, 'longitude': 3.3, 'radius_meters': 100}})
    payload = {'location': {'latitude': 6.5, 'longitude': 3.3, 'accuracy_meters': 10, 'captured_at': datetime.now(UTC).isoformat()}, 'idempotency_key': str(uuid4())}
    path = f'/api/v1/task-assignments/{assignment}'
    assert client.post(path + '/submissions', headers=headers(member), json=payload).status_code == 201
    with sessions() as db:
        assert db.query(ImpactTransaction).count() == 0
        evidence = db.query(TaskSubmission).one().location_evidence
        assert evidence['verified'] and 'latitude' not in evidence
    for _ in range(2):
        assert client.post(path + '/verify', headers=headers(admin), json={'approve': True}).status_code == 200
    with sessions() as db:
        assert db.query(ImpactTransaction).one().points == 5
    assert client.post(path + '/submissions', headers=headers(member), json=payload).status_code == 201


def test_task_detail_safe_and_survey_default(context):
    client, (admin, member, outsider, community), _ = context
    task, _ = create_assigned(context, task_type='quiz', task_config=quiz())
    assert '"correct"' not in client.get(f'/api/v1/tasks/{task}', headers=headers(member)).text
    assert client.get(f'/api/v1/tasks/{task}', headers=headers(outsider)).status_code == 403
    task, assignment = create_assigned(context, task_type='survey', task_config={'assessment': {'questions': [{'id': 'opinion', 'prompt': 'Thoughts?', 'kind': 'long_text', 'required': False}]}}, verification_required=False)
    detail = client.get(f'/api/v1/tasks/{task}', headers=headers(member)).json()
    assert detail['task_config']['assessment']['max_attempts'] == 1
    assert client.post(f'/api/v1/task-assignments/{assignment}/submissions', headers=headers(member), json={}).status_code == 201
    bad = client.post(f'/api/v1/communities/{community}/tasks', headers=headers(admin), json={'title': 'Unsafe URL', 'description': 'Do not allow script links', 'task_type': 'video', 'task_config': {'video_url': 'javascript:alert(1)'}})
    assert bad.status_code == 422


def test_nigeria_location_validation_preserves_legacy():
    from src.geography import nigeria_locations
    from src.schemas.event import VenueInput
    data = nigeria_locations()
    assert len(data) == 37 and sum(map(len, data.values())) == 774
    VenueInput(name='Hall', address='Road', region='Enugu', lga='Enugu South', city='Independent town')
    VenueInput(name='Hall', address='Road', region='Historic region', city='Old town')
    with pytest.raises(ValueError):
        VenueInput(name='Hall', address='Road', region='Lagos', lga='Enugu South')


def test_event_geofence_requires_radius_for_server_enforcement():
    """Check-in compares distance and accuracy against the radius, so enabling GPS must persist one."""
    from src.schemas.event import EventCreate
    now = datetime.now(UTC)
    base = {'community_id': uuid4(), 'title': 'Community meetup', 'description': 'Long enough description',
            'category': 'Community', 'starts_at': now + timedelta(days=1), 'ends_at': now + timedelta(days=1, hours=2),
            'location_type': 'physical',
            'venue': {'name': 'Hall', 'address': 'Road', 'latitude': '6.5', 'longitude': '3.3'}}
    assert EventCreate(**base, geofence_enabled=True, geofence_radius_meters=100).geofence_radius_meters == 100
    with pytest.raises(ValueError):
        EventCreate(**base, geofence_enabled=True)
    # Coordinates remain required, and a non-geofenced event still needs no radius.
    with pytest.raises(ValueError):
        EventCreate(**{**base, 'venue': {'name': 'Hall', 'address': 'Road'}}, geofence_enabled=True, geofence_radius_meters=100)
    assert EventCreate(**base).geofence_radius_meters is None


def test_promotions_rbac_schedule_and_private_task_delivery(context):
    client, (admin, member, outsider, community), sessions = context
    task, _ = create_assigned(context)
    with sessions() as db:
        db.get(User, admin).role = PlatformRole.SUPER_ADMIN
        db.get(Community, community).is_public = True; db.commit()
    now = datetime.now(UTC)
    payload = {'content_type': 'task', 'content_id': task, 'classification': 'sponsored', 'surface': 'home', 'is_active': True, 'starts_at': (now - timedelta(hours=1)).isoformat(), 'ends_at': (now + timedelta(days=1)).isoformat(), 'reason': 'Approved community activity'}
    assert client.post('/api/v1/admin/promotions', headers=headers(member), json=payload).status_code == 403
    response = client.post('/api/v1/admin/promotions', headers=headers(admin), json=payload)
    assert response.status_code == 201, response.text
    promotion = response.json()['id']
    assert client.get('/api/v1/promotions/public?surface=home').json() == []
    assert client.get('/api/v1/promotions/me?surface=home', headers=headers(outsider)).json() == []
    visible = client.get('/api/v1/promotions/me?surface=home', headers=headers(member))
    assert visible.status_code == 200 and visible.json()[0]['classification'] == 'sponsored'
    assert 'task_config' not in visible.text
    assert client.post('/api/v1/admin/promotions', headers=headers(admin), json={**payload, 'surface': 'attendance'}).status_code == 422
    with sessions() as db:
        db.get(Community, community).is_public = False; db.commit()
    assert client.get('/api/v1/promotions/me?surface=home', headers=headers(member)).json() == []
    # Can deactivate a placement even if its content has since become ineligible.
    assert client.post(f'/api/v1/admin/promotions/{promotion}/deactivate', headers=headers(admin), json={'reason': 'Content made private'}).status_code == 200


def test_promotion_delivery_rechecks_suspended_content_and_suppresses_duplicates(context):
    """Suspending promoted content stops delivery without recreating the placement, and one item is never delivered twice."""
    from src.models import Event, EventStatus, LocationType
    client, (admin, _, _, community), sessions = context
    with sessions() as db:
        db.get(User, admin).role = PlatformRole.SUPER_ADMIN
        db.get(Community, community).is_public = True
        now = datetime.now(UTC)
        event = Event(community_id=community, organizer_id=admin, title='Promoted event', slug='promoted-event',
                      description='Promoted event content', category='community', starts_at=now,
                      ends_at=now + timedelta(days=1), location_type=LocationType.ONLINE, status=EventStatus.PUBLISHED)
        db.add(event); db.commit(); event_id = event.id
    payload = {'content_type': 'event', 'content_id': str(event_id), 'classification': 'featured', 'surface': 'discover',
               'is_active': True, 'starts_at': (now - timedelta(hours=1)).isoformat(),
               'ends_at': (now + timedelta(hours=2)).isoformat(), 'priority': 5, 'reason': 'Editorial placement'}
    assert client.post('/api/v1/admin/promotions', headers=headers(admin), json=payload).status_code == 201
    # A conflicting second placement for the same content must not duplicate the delivery.
    assert client.post('/api/v1/admin/promotions', headers=headers(admin), json={**payload, 'classification': 'sponsored', 'priority': 9}).status_code == 201
    delivered = client.get('/api/v1/promotions/public?surface=discover').json()
    assert [row['content_id'] for row in delivered] == [str(event_id)] and delivered[0]['classification'] == 'sponsored'
    # Underlying content state is rechecked on every delivery; the promotion record is untouched.
    governance = '/api/v1/admin/platform/governance'
    assert client.post(f'{governance}/event/{event_id}/moderation', headers=headers(admin), json={'suspended': True, 'reason': 'Policy review'}).status_code == 200
    assert client.get('/api/v1/promotions/public?surface=discover').json() == []
    assert client.post(f'{governance}/event/{event_id}/moderation', headers=headers(admin), json={'suspended': False, 'reason': 'Policy review closed'}).status_code == 200
    assert [row['content_id'] for row in client.get('/api/v1/promotions/public?surface=discover').json()] == [str(event_id)]


def test_promotion_schedule_normalizes_client_offset_to_utc(context):
    """A non-UTC offset must not shift the placement window or delay delivery."""
    from datetime import timezone

    from src.models.promotion import Promotion
    client, (admin, member, _, community), sessions = context
    with sessions() as db:
        db.get(User, admin).role = PlatformRole.SUPER_ADMIN
        db.get(Community, community).is_public = True; db.commit()
    task, _ = create_assigned(context)
    now = datetime.now(UTC)
    lagos = timezone(timedelta(hours=1))
    starts_at, ends_at = now - timedelta(minutes=5), now + timedelta(hours=5)
    payload = {'content_type': 'task', 'content_id': task, 'classification': 'featured', 'surface': 'home',
               'is_active': True, 'starts_at': starts_at.astimezone(lagos).isoformat(),
               'ends_at': ends_at.astimezone(lagos).isoformat(), 'reason': 'Offset schedule check'}
    created = client.post('/api/v1/admin/promotions', headers=headers(admin), json=payload)
    assert created.status_code == 201, created.text
    with sessions() as db:
        stored = db.get(Promotion, UUID(created.json()['id']))
        assert abs(stored.starts_at.replace(tzinfo=UTC) - starts_at) < timedelta(seconds=1)
        assert abs(stored.ends_at.replace(tzinfo=UTC) - ends_at) < timedelta(seconds=1)
    # The window is active in absolute time, so it must deliver despite the client's +01:00 offset.
    assert [row['content_id'] for row in client.get('/api/v1/promotions/me?surface=home', headers=headers(member)).json()] == [task]
