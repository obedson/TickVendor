"""Focused staging regressions: policy, assessments, secrecy and replay integrity."""
from uuid import uuid4

import pytest
from sqlalchemy import select

from src.models import (
    AuthSession,
    ImpactTransaction,
    Membership,
    MembershipStatus,
    Notification,
    PlatformRole,
    PointCeiling,
    PointRule,
    Task,
    TaskAssignment,
    TaskSubmission,
    User,
)
from tests.test_community_management import headers, setup


@pytest.fixture
def context(tmp_path):
    engine, client, ids, sessions = setup(tmp_path)
    _admin, _member, _outsider, community = ids
    with sessions() as db:
        db.add(PointCeiling(source_type='task_completion', maximum_points=20))
        db.add(PointRule(community_id=community, source_type='task_completion', points=5))
        db.commit()
    yield client, ids, sessions
    engine.dispose()


def create_assigned(context, **values):
    client, (admin, member, _, community), _ = context
    payload = {'title': 'Training task', 'description': 'Complete the activity', 'impact_point_reward': 5,
               'required_evidence_types': [], 'verification_required': True}
    payload.update(values)
    created = client.post(f'/api/v1/communities/{community}/tasks', headers=headers(admin), json=payload)
    assert created.status_code == 201, created.text
    task = created.json()['id']
    assigned = client.post(f'/api/v1/tasks/{task}/assignments', headers=headers(admin), json={'assignee_id': str(member)})
    assert assigned.status_code == 201, assigned.text
    return task, assigned.json()['id']


def quiz():
    return {'assessment': {'questions': [{'id': 'q1', 'prompt': 'Pick B', 'kind': 'single',
                                          'choices': ['A', 'B'], 'correct': [1]}],
                           'passing_score': 100, 'max_attempts': 2}}


def test_quiz_secrecy_attempts_replay_and_exact_reward(context):
    client, (admin, member, outsider, community), sessions = context
    _task, assignment = create_assigned(context, task_type='quiz', task_config=quiz())
    for path in (f'communities/{community}/tasks', 'task-assignments/me/details'):
        response = client.get('/api/v1/' + path, headers=headers(member))
        assert response.status_code == 200
        assert '"correct"' not in response.text
    assert client.get(f'/api/v1/communities/{community}/tasks?management=true', headers=headers(member)).status_code == 403
    assert client.get(f'/api/v1/communities/{community}/tasks', headers=headers(outsider)).status_code == 403
    base = f'/api/v1/task-assignments/{assignment}'
    wrong = {'answers': {'q1': [0]}, 'idempotency_key': str(uuid4())}
    first = client.post(base + '/submissions', headers=headers(member), json=wrong)
    assert first.status_code == 201, first.text
    assert first.json()['assessment_result']['passed'] is False
    replay = client.post(base + '/submissions', headers=headers(member), json=wrong)
    assert replay.json()['id'] == first.json()['id']
    assert client.post(base + '/verify', headers=headers(admin), json={'approve': True}).status_code == 409
    correct = {'answers': {'q1': [1]}, 'idempotency_key': str(uuid4())}
    assert client.post(base + '/submissions', headers=headers(outsider), json=correct).status_code == 403
    passed = client.post(base + '/submissions', headers=headers(member), json=correct)
    assert passed.status_code == 201 and passed.json()['assessment_result']['score'] == 100
    assert client.get(base + '/attempts', headers=headers(outsider)).status_code == 404
    assert len(client.get(base + '/attempts', headers=headers(member)).json()) == 2
    for _ in range(2):
        assert client.post(base + '/verify', headers=headers(admin), json={'approve': True}).status_code == 200
    with sessions() as db:
        tx = db.scalars(select(ImpactTransaction)).one()
        assert tx.points == 5 and tx.idempotency_key == f'task:{assignment}:verified'
        notification = db.scalars(select(Notification).where(Notification.notification_type == 'task_verified')).one()
        assert 'Training task' in notification.message and '5 Impact Points' in notification.message
        from src.services.recognition import user_metrics
        metrics = user_metrics(db, member, community)
        assert metrics['task_count'] == 1 and metrics['impact_points'] == 5
        assert db.query(TaskSubmission).count() == 2
        assert db.query(TaskAssignment).filter_by(status='VERIFIED').count() == 1


def test_quiz_lockout_and_invalid_config(context):
    client, (admin, member, _, community), _ = context
    invalid = client.post(f'/api/v1/communities/{community}/tasks', headers=headers(admin),
                          json={'title': 'Quiz', 'description': 'Missing questions', 'task_type': 'quiz'})
    assert invalid.status_code == 422
    _, assignment = create_assigned(context, task_type='quiz', task_config=quiz())
    for expected in (201, 201, 409):
        response = client.post(f'/api/v1/task-assignments/{assignment}/submissions', headers=headers(member),
                               json={'answers': {'q1': [0]}, 'idempotency_key': str(uuid4())})
        assert response.status_code == expected, response.text


def test_checkpoint_secrecy_and_case_insensitive_n_of_m(context):
    client, (_, member, _, community), _ = context
    config = {'video_url': 'https://www.youtube.com/watch?v=abc', 'checkpoints': {
        'items': [{'id': 'c1', 'position': '02:15', 'prompt': 'First code', 'expected': 'IMPACT'},
                  {'id': 'c2', 'position': '06:40', 'prompt': 'Second code', 'expected': 'LEARN'}],
        'minimum_correct': 1, 'max_attempts': 2}}
    _, assignment = create_assigned(context, task_type='video', task_config=config)
    response = client.get(f'/api/v1/communities/{community}/tasks', headers=headers(member))
    assert 'IMPACT' not in response.text and '"expected"' not in response.text
    response = client.post(f'/api/v1/task-assignments/{assignment}/submissions', headers=headers(member),
                           json={'answers': {'c1': ' impact ', 'c2': 'wrong'}})
    assert response.status_code == 201 and response.json()['assessment_result']['passed'] is True


@pytest.mark.parametrize('opinion', [0, 1])
def test_surveys_reward_completion_not_opinion(context, opinion):
    client, (admin, member, _, community), sessions = context
    config = {'assessment': {'questions': [{'id': 'q1', 'prompt': 'Your view?', 'kind': 'single',
                                            'choices': ['Agree', 'Disagree']}]}}
    _, assignment = create_assigned(context, task_type='survey', task_config=config)
    response = client.post(f'/api/v1/task-assignments/{assignment}/submissions', headers=headers(member),
                           json={'answers': {'q1': [opinion]}})
    assert response.status_code == 201 and 'score' not in response.json()['assessment_result']
    assert client.post(f'/api/v1/task-assignments/{assignment}/verify', headers=headers(admin), json={'approve': True}).status_code == 200
    with sessions() as db:
        assert db.scalars(select(ImpactTransaction)).one().points == 5
    config['assessment']['questions'][0]['correct'] = [0]
    response = client.post(f'/api/v1/communities/{community}/tasks', headers=headers(admin),
                           json={'title': 'Bad survey', 'description': 'Preferred opinion', 'task_type': 'survey', 'task_config': config})
    assert response.status_code == 422


def test_physical_evidence_membership_rejection_and_latest_queue(context):
    client, (admin, member, _, community), sessions = context
    _, assignment = create_assigned(context, task_type='physical')
    base = f'/api/v1/task-assignments/{assignment}'
    assert client.post(base + '/submissions', headers=headers(member), json={}).status_code == 201
    for _ in range(2):
        assert client.post(base + '/verify', headers=headers(admin), json={'approve': False, 'reason': 'Please describe the work'}).status_code == 200
    with sessions() as db:
        notice = db.scalars(select(Notification).where(Notification.notification_type == 'task_rejected')).one()
        assert 'Please describe the work' in notice.message
        membership = db.scalar(select(Membership).where(Membership.user_id == member, Membership.community_id == community))
        membership.status = MembershipStatus.INVITED
        db.commit()
    assert client.post(base + '/submissions', headers=headers(member), json={}).status_code == 403
    with sessions() as db:
        membership = db.scalar(select(Membership).where(Membership.user_id == member, Membership.community_id == community))
        membership.status = MembershipStatus.ACTIVE
        db.commit()
    assert client.post(base + '/submissions', headers=headers(member), json={'evidence_text': 'Revised work'}).status_code == 201
    queue = client.get(f'/api/v1/communities/{community}/task-verification-queue', headers=headers(admin))
    assert len(queue.json()) == 1 and queue.json()[0]['evidence_text'] == 'Revised work'


def test_point_hierarchy_history_and_no_uncapped_community_rules(context):
    client, (admin, member, outsider, community), sessions = context
    base = f'/api/v1/admin/communities/{community}/point-rules'
    assert client.put(base, headers=headers(admin), json={'source_type': 'task_completion', 'points': 21}).status_code == 422
    assert client.put(base, headers=headers(admin), json={'source_type': 'new_source', 'points': 1}).status_code == 422
    assert client.put(base, headers=headers(outsider), json={'source_type': 'task_completion', 'points': 5}).status_code == 403
    response = client.post(f'/api/v1/communities/{community}/tasks', headers=headers(admin), json={'title': 'Too much', 'description': 'Reward mismatch', 'impact_point_reward': 20})
    assert response.status_code == 422
    with sessions() as db:
        db.add(PointRule(source_type='task_completion', points=20))
        db.commit()
    task, assignment = create_assigned(context)
    client.post(f'/api/v1/task-assignments/{assignment}/submissions', headers=headers(member), json={})
    assert client.post(f'/api/v1/task-assignments/{assignment}/verify', headers=headers(admin), json={'approve': True}).status_code == 200
    with sessions() as db:
        user = db.get(User, outsider); user.role = PlatformRole.SUPER_ADMIN; db.commit()
    ceiling = {'source_type': 'task_completion', 'maximum_points': 3, 'reason': 'Lower future awards'}
    assert client.put('/api/v1/point-ceilings', headers=headers(admin), json=ceiling).status_code == 403
    assert client.put('/api/v1/point-ceilings', headers=headers(outsider), json=ceiling).status_code == 200
    listing = client.get(f'/api/v1/communities/{community}/tasks', headers=headers(member)).json()
    assert next(t for t in listing if t['id'] == task)['impact_point_reward'] == 3
    with sessions() as db:
        assert db.scalars(select(ImpactTransaction)).one().points == 5
        db.get(Task, task).reward_mode = 'legacy_rule'; db.get(Task, task).impact_point_reward = 20; db.commit()
    assert client.get(f'/api/v1/communities/{community}/tasks', headers=headers(member)).json()[0]['impact_point_reward'] == 3


def test_suspended_login_only_after_valid_credentials(context):
    client, (_, member, _, _), sessions = context
    with sessions() as db:
        db.get(User, member).is_active = False; db.commit()
    path = '/api/v1/auth/login'
    assert client.post(path, json={'email': 'member@example.com', 'password': 'wrong-password'}).status_code == 401
    assert client.post(path, json={'email': 'unknown@example.com', 'password': 'wrong-password'}).status_code == 401
    suspended = client.post(path, json={'email': 'member@example.com', 'password': 'password-password'})
    assert suspended.status_code == 403 and 'suspended' in suspended.text
    assert 'access_token' not in suspended.text
    with sessions() as db:
        assert db.query(AuthSession).count() == 0
        db.get(User, member).is_active = True; db.commit()
    assert client.post(path, json={'email': 'member@example.com', 'password': 'password-password'}).status_code == 200


def test_legacy_rule_and_explicit_auto_awards_preserve_retry_integrity(context):
    client, (admin, member, _, community), sessions = context
    legacy, first = create_assigned(context)
    with sessions() as db:
        task = db.get(Task, legacy)
        task.reward_mode = 'legacy_rule'; task.impact_point_reward = 20
        db.commit()
    base = f'/api/v1/task-assignments/{first}'
    assert client.post(base + '/submissions', headers=headers(member), json={}).status_code == 201
    with sessions() as db:
        rule = db.scalar(select(PointRule).where(PointRule.community_id == community))
        rule.is_active = False; db.commit()
    assert client.post(base + '/verify', headers=headers(admin), json={'approve': True}).status_code == 409
    with sessions() as db:
        assert db.query(ImpactTransaction).count() == 0
        db.scalar(select(PointRule).where(PointRule.community_id == community)).is_active = True; db.commit()
    assert client.post(base + '/verify', headers=headers(admin), json={'approve': True}).status_code == 200
    _, second = create_assigned(context, impact_point_reward=3, verification_required=False)
    payload = {'idempotency_key': str(uuid4())}
    second_base = f'/api/v1/task-assignments/{second}/submissions'
    original = client.post(second_base, headers=headers(member), json=payload)
    repeat = client.post(second_base, headers=headers(member), json=payload)
    assert original.status_code == 201 and repeat.json()['id'] == original.json()['id']
    assert client.post(second_base, headers=headers(member), json={}).status_code == 409
    assert client.post(second_base, headers=headers(member), json={**payload, 'evidence_text': 'changed'}).status_code == 409
    with sessions() as db:
        assert sorted(db.scalars(select(ImpactTransaction.points))) == [3, 5]
        assert db.query(Notification).filter_by(notification_type='task_verified').count() == 2


def test_global_rule_uniqueness_and_cap_constraint(context):
    from sqlalchemy.exc import IntegrityError

    _, _, sessions = context
    with sessions() as db:
        db.add(PointRule(source_type='global_test', points=1)); db.commit()
        db.add(PointRule(source_type='global_test', points=2))
        with pytest.raises(IntegrityError): db.commit()
        db.rollback()
        db.add(PointCeiling(source_type='invalid_cap', maximum_points=-1))
        with pytest.raises(IntegrityError): db.commit()
        db.rollback()
