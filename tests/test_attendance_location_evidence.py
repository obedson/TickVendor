from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.api.attendance import attendance_roster
from src.models import Attendance, AttendanceVerification, AuditLog, ImpactTransaction, TicketStatus
from src.schemas.attendance import AttendanceCheckIn
from src.services.ticket_attendance import self_check_in
from tests.test_ticket_holders_and_entitlements import INSIDE, OUTSIDE, issue, make_db, setup


def test_outside_location_survives_request_rollback_and_can_retry(tmp_path):
    engine = make_db(tmp_path)
    with Session(engine, expire_on_commit=False) as db:
        organizer, buyer, _, outsider, _, event = setup(db)
        _, _, ticket = issue(db, event, buyer)
        with pytest.raises(HTTPException) as error:
            self_check_in(db, event.id, ticket.id, buyer, OUTSIDE)
        assert error.value.status_code == 422
        assert 'allowed radius: 100 m' in error.value.detail
        db.rollback()  # Match exception cleanup at the HTTP request boundary.
        assert db.query(Attendance).count() == 0
        assert db.query(ImpactTransaction).count() == 0
        assert ticket.status == TicketStatus.ACTIVE
        entry = db.query(AuditLog).filter_by(action='attendance.location_submitted').one()
        assert entry.metadata_json['outcome'] == 'outside_geofence'
        row = attendance_roster(event.id, db, organizer, limit=100, offset=0)[0]
        evidence = row['latest_location_attempt']
        assert evidence['latitude'] == float(OUTSIDE.latitude)
        assert evidence['longitude'] == float(OUTSIDE.longitude)
        assert evidence['distance_meters'] is not None
        assert row['attendance_status'] == 'not_checked_in'
        with pytest.raises(HTTPException) as forbidden:
            attendance_roster(event.id, db, outsider, limit=100, offset=0)
        assert forbidden.value.status_code == 403
        result = self_check_in(db, event.id, ticket.id, buyer, INSIDE)
        assert result['status'] == 'gps_verified'
        assert ticket.status == TicketStatus.USED
        count = db.query(AuditLog).filter_by(action='attendance.location_submitted').count()
        self_check_in(db, event.id, ticket.id, buyer, INSIDE)
        assert db.query(AuditLog).filter_by(action='attendance.location_submitted').count() == count
        row = attendance_roster(event.id, db, organizer, limit=100, offset=0)[0]
        assert row['latest_location_attempt']['outcome'] == 'verified'
        assert len(row['location_evidence']) == 1
        assert 10 < row['location_evidence'][0]['distance_meters'] < 20
        assert row['location_evidence'][0]['accuracy_meters'] == 12
    engine.dispose()


@pytest.mark.parametrize(('point', 'outcome'), [
    (AttendanceCheckIn(latitude='6.44', longitude='7.49', accuracy_meters=500), 'low_accuracy'),
    (AttendanceCheckIn(latitude='6.44', longitude='7.49'), 'accuracy_missing'),
])
def test_uncertain_inside_location_waits_for_organizer_without_using_ticket(tmp_path, point, outcome):
    from src.services.attendance import organizer_verify

    engine = make_db(tmp_path)
    with Session(engine, expire_on_commit=False) as db:
        organizer, buyer, _, _, _, event = setup(db)
        _, _, ticket = issue(db, event, buyer)
        result = self_check_in(db, event.id, ticket.id, buyer, point)
        assert result['pending_review'] is True
        assert result['status'] == 'checked_in'
        assert ticket.status == TicketStatus.ACTIVE
        assert db.query(ImpactTransaction).count() == 0
        attendance = db.query(Attendance).one()
        assert attendance.flagged_for_review is True
        evidence = db.query(AttendanceVerification).one()
        assert evidence.is_valid is False
        assert db.query(AuditLog).filter_by(action='attendance.location_submitted').one().metadata_json['outcome'] == outcome
        organizer_verify(db, attendance, organizer, True, 'Confirmed participant at venue')
        assert attendance.status.value == 'organizer_verified'
        assert attendance.flagged_for_review is False
        assert ticket.status == TicketStatus.USED
        replay = self_check_in(db, event.id, ticket.id, buyer, point)
        assert replay['attendance_id'] == result['attendance_id']
        assert replay['status'] == 'organizer_verified'
        assert replay['pending_review'] is False
        assert replay['viable_methods'] == ['organizer']
    engine.dispose()


def test_http_failed_attempt_then_success_and_checkout(tmp_path):
    from fastapi.testclient import TestClient

    from src.database import get_db
    from src.main import create_app
    from src.security import create_access_token

    engine = make_db(tmp_path)
    with Session(engine, expire_on_commit=False) as db:
        organizer, buyer, _, outsider, _, event = setup(db)
        _, _, ticket = issue(db, event, buyer)
        event_id, ticket_id = event.id, ticket.id
        buyer_headers = {'Authorization': f'Bearer {create_access_token(buyer.id, "participant")}'}
        admin_headers = {'Authorization': f'Bearer {create_access_token(organizer.id, "participant")}'}
        outsider_headers = {'Authorization': f'Bearer {create_access_token(outsider.id, "participant")}'}
    app = create_app()

    def override():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        path = f'/api/v1/events/{event_id}/tickets/{ticket_id}'
        pending = client.post(path + '/check-in', headers=buyer_headers,
                              json={'latitude': 6.44, 'longitude': 7.49, 'accuracy_meters': 500})
        assert pending.status_code == 200 and pending.json()['pending_review'] is True
        roster_path = f'/api/v1/events/{event_id}/attendance/roster'
        roster = client.get(roster_path, headers=admin_headers)
        assert roster.status_code == 200
        assert roster.json()[0]['latest_location_attempt']['distance_meters'] == 0
        assert client.get(roster_path, headers=outsider_headers).status_code == 403
        assert client.get(roster_path).status_code == 401
        attendance_id = pending.json()['attendance_id']
        reviewed = client.post(f'/api/v1/events/{event_id}/attendance/{attendance_id}/review',
                               headers=admin_headers, json={'outcome': 'confirmed', 'reason': 'Confirmed at venue'})
        assert reviewed.status_code == 200, reviewed.text
        assert reviewed.json()['status'] == 'organizer_verified'
        point = INSIDE.model_dump(mode='json')
        accepted = client.post(path + '/check-in', headers=buyer_headers, json=point)
        assert accepted.status_code == 200 and accepted.json()['status'] == 'organizer_verified'
        checkout = client.post(path + '/check-out', headers=buyer_headers, json=point)
        assert checkout.status_code == 200, checkout.text
        assert checkout.json()['checked_out_at'] is not None
        roster = client.get(roster_path, headers=admin_headers).json()[0]
        assert len(roster['location_evidence']) == 2
        assert roster['latest_location_attempt']['operation'] == 'checkout'
    engine.dispose()


def test_radius_boundary_does_not_round_outside_point_into_geofence(tmp_path):
    from src.services.attendance import haversine_meters
    from src.services.attendance_location import location_evidence

    engine = make_db(tmp_path)
    with Session(engine) as db:
        *_, event = setup(db)
        point = AttendanceCheckIn(latitude=Decimal('6.44089933'), longitude='7.49', accuracy_meters=1)
        distance = haversine_meters(point.latitude, point.longitude, event.venue.latitude, event.venue.longitude)
        assert distance > 100
        assert location_evidence(event, point)['outcome'] == 'outside_geofence'
    engine.dispose()
