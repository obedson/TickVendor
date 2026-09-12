"""Archives preserve records and cannot target another participant's evidence."""
from datetime import UTC, datetime

from sqlalchemy import inspect, select

from src.models import (
    Attendance,
    AttendanceStatus,
    Badge,
    BadgeAward,
    ImpactTransaction,
    ImpactTransactionStatus,
    Milestone,
    MilestoneAward,
    Notification,
    OpportunityRegistration,
    OpportunityRegistrationStatus,
    PersonalArchive,
    TaskAssignment,
    TaskAssignmentStatus,
    Ticket,
    TicketStatus,
    TicketType,
)
from tests.test_community_management import headers, setup
from tests.test_platform_moderation import content


def test_owned_eligible_records_archive_restore_without_domain_mutation(tmp_path):
    engine, client, (admin, member, outsider, community), sessions = setup(tmp_path)
    event, opportunity, task = content(sessions, community, admin)
    with sessions() as db:
        tt = TicketType(event_id=event, name='Free', quantity=20)
        db.add(tt); db.flush()
        ticket = Ticket(event_id=event,ticket_type_id=tt.id,attendee_id=member,public_id='ARCHIVE-USED',qr_token='archive-qr-token-'*3,status=TicketStatus.USED)
        active = Ticket(event_id=event,ticket_type_id=tt.id,attendee_id=member,public_id='ARCHIVE-ACTIVE',qr_token='active-qr-token-'*3,status=TicketStatus.ACTIVE)
        failed = Ticket(event_id=event,ticket_type_id=tt.id,attendee_id=member,public_id='ARCHIVE-FAILED',qr_token='failed-qr-token-'*3,status=TicketStatus.PENDING_PAYMENT)
        notification = Notification(user_id=member,notification_type='notice',title='Notice',message='History')
        assignment = TaskAssignment(task_id=task,assignee_id=member,assigned_by_id=admin,status=TaskAssignmentStatus.VERIFIED)
        registration = OpportunityRegistration(opportunity_id=opportunity,participant_id=member,status=OpportunityRegistrationStatus.VERIFIED)
        db.add_all([ticket,active,failed,notification,assignment,registration]); db.commit()
        targets = [('ticket',ticket.id),('task',assignment.id),('opportunity',registration.id),('notification',notification.id)]
        active_id, failed_id = active.id, failed.id
        attendance = Attendance(event_id=event, user_id=member, ticket_id=ticket.id, status=AttendanceStatus.QR_VERIFIED)
        points = ImpactTransaction(user_id=member, community_id=community, event_id=event, points=10,
            source_type='attendance', idempotency_key='archive-impact', reason='Attendance evidence', status=ImpactTransactionStatus.POSTED)
        badge = Badge(community_id=community, name='Attendance badge', slug='archive-badge', category='attendance')
        milestone = Milestone(community_id=community, name='Attendance milestone', slug='archive-milestone')
        db.add_all([attendance, points, badge, milestone]); db.flush()
        db.add_all([BadgeAward(user_id=member, badge_id=badge.id, idempotency_key='archive-badge-award', awarded_at=datetime.now(UTC)),
                    MilestoneAward(user_id=member, milestone_id=milestone.id, idempotency_key='archive-milestone-award', awarded_at=datetime.now(UTC))])
        db.commit()
    evidence_models = (Ticket, Attendance, ImpactTransaction, BadgeAward, MilestoneAward, TaskAssignment, OpportunityRegistration, Notification)

    def evidence_snapshot():
        with sessions() as db:
            return {model.__tablename__: [tuple(getattr(row, column.key) for column in inspect(model).columns)
                for row in db.scalars(select(model).order_by(model.id))] for model in evidence_models}

    original_evidence = evidence_snapshot()
    assert client.post(f'/api/v1/me/archive/ticket/{active_id}', headers=headers(member)).status_code == 409
    assert client.post(f'/api/v1/me/archive/ticket/{failed_id}', headers=headers(member)).status_code == 404
    for kind, target in targets:
        url = f'/api/v1/me/archive/{kind}/{target}'
        assert client.post(url, headers=headers(outsider)).status_code == 404
        assert client.post(url, headers=headers(member)).status_code == 204
        assert client.post(url, headers=headers(member)).status_code == 204
        assert client.delete(url, headers=headers(outsider)).status_code == 404
        assert any(item['id'] == str(target) and item['archived'] for item in client.get(f'/api/v1/me/personal-items/{kind}', headers=headers(member)).json())
    assert len(client.get('/api/v1/me/archive', headers=headers(member)).json()) == 4
    assert evidence_snapshot() == original_evidence
    assert client.get('/api/v1/me/archive', headers=headers(outsider)).json() == []
    assert all(item['id'] != str(failed_id) for item in client.get('/api/v1/me/personal-items/ticket',headers=headers(member)).json())
    with sessions() as db:
        assert db.get(Ticket,targets[0][1]).status == TicketStatus.USED
        assert db.get(Ticket,targets[0][1]).qr_token == 'archive-qr-token-'*3
        assert db.get(TaskAssignment,targets[1][1]).status == TaskAssignmentStatus.VERIFIED
        assert db.get(OpportunityRegistration,targets[2][1]).status == OpportunityRegistrationStatus.VERIFIED
        assert db.get(Notification,targets[3][1]).message == 'History'
    for kind,target in targets:
        assert client.delete(f'/api/v1/me/archive/{kind}/{target}',headers=headers(member)).status_code == 204
        assert client.delete(f'/api/v1/me/archive/{kind}/{target}',headers=headers(member)).status_code == 204
    assert client.post(f'/api/v1/me/archive/attendance/{targets[0][1]}',headers=headers(member)).status_code == 422
    with sessions() as db:
        assert db.query(PersonalArchive).count() == 0
        assert db.query(Ticket).count() == 3
    assert evidence_snapshot() == original_evidence
    engine.dispose()
