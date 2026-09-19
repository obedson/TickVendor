"""Organizer least-privilege tests.

Organizers operate programs; Admins govern the community. These tests pin the boundary between
the two: what an Organizer may still do (run their own events and tasks), what they may no longer
do (browse the community directory, act on a colleague's event or task), and what an Admin keeps.

Four surfaces are covered:

* constrained member lookup (:mod:`src.api.community_management`)
* event-scoped attendance authority (:mod:`src.authorization`, :mod:`src.services.attendance`)
* EventStaff delegation, the previously missing write path (:mod:`src.services.event_staff`)
* task ownership (:mod:`src.services.task`, :mod:`src.services.task_bulk`, :mod:`src.api.tasks`)

Three further surfaces pin the follow-up corrections:

* ticket validation reachability for appointed door staff (:mod:`src.services.ticket`)
* event-scoped analytics, community analytics left Admin-only (:mod:`src.services.analytics`)
* EventStaff role semantics — which staff role carries which job (:mod:`src.services.entitlement`,
  :mod:`src.api.ticket_operations`)
"""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import (
    Attendance,
    AttendanceStatus,
    AuditLog,
    Community,
    Event,
    EventStaff,
    EventStaffRole,
    LocationType,
    Membership,
    MembershipRole,
    MembershipStatus,
    Organization,
    Profile,
    ProfileVisibility,
    Task,
    TaskAssignment,
    TaskAssignmentStatus,
    TaskSubmission,
    Ticket,
    TicketAssignmentState,
    TicketStatus,
    TicketType,
    User,
)
from src.security import create_access_token, hash_password

API = "/api/v1"


def setup(tmp_path):
    """One community whose event belongs to ``owner``, plus a second community to cross into.

    Community A membership: ``admin`` (ADMIN), ``owner`` and ``organizer`` (ORGANIZER),
    ``member`` and ``member_two`` (MEMBER), ``suspended`` (MEMBER, suspended membership),
    ``inactive`` (MEMBER, deactivated user account), ``private`` (MEMBER, private profile).
    ``outsider`` is an ORGANIZER of community B and of nothing else.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'organizer-least-privilege.db'}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        people = {
            "admin": User(email="admin@example.com", password_hash=hash_password("password-password")),
            "owner": User(email="owner@example.com", password_hash=hash_password("password-password")),
            "organizer": User(email="organizer@example.com", password_hash=hash_password("password-password")),
            "member": User(email="member@example.com", password_hash=hash_password("password-password")),
            "member_two": User(email="member-two@example.com", password_hash=hash_password("password-password")),
            "suspended": User(email="suspended@example.com", password_hash=hash_password("password-password")),
            "inactive": User(email="inactive@example.com", password_hash=hash_password("password-password"),
                             is_active=False),
            "private": User(email="private@example.com", password_hash=hash_password("password-password")),
            "outsider": User(email="outsider@example.com", password_hash=hash_password("password-password")),
        }
        db.add_all(list(people.values()))
        db.flush()
        db.add_all([
            Profile(user_id=people["admin"].id, username="lp-admin", display_name="Ada Admin"),
            Profile(user_id=people["owner"].id, username="lp-owner", display_name="Owen Owner"),
            Profile(user_id=people["organizer"].id, username="lp-organizer", display_name="Olive Organizer"),
            Profile(user_id=people["member"].id, username="lp-member", display_name="Mona Member"),
            Profile(user_id=people["member_two"].id, username="lp-member-two", display_name="Miles Member"),
            Profile(user_id=people["suspended"].id, username="lp-suspended", display_name="Sonia Suspended"),
            Profile(user_id=people["inactive"].id, username="lp-inactive", display_name="Ivan Inactive"),
            Profile(user_id=people["private"].id, username="lp-private", display_name="Priya Private",
                    visibility=ProfileVisibility.PRIVATE),
            Profile(user_id=people["outsider"].id, username="lp-outsider", display_name="Oscar Outsider"),
        ])
        organization = Organization(owner_id=people["admin"].id, name="Org", slug="lp-org")
        other_organization = Organization(owner_id=people["outsider"].id, name="Other Org", slug="lp-other-org")
        db.add_all([organization, other_organization])
        db.flush()
        community = Community(organization_id=organization.id, name="LP Community", slug="lp-community")
        other_community = Community(organization_id=other_organization.id, name="Other Community", slug="lp-other")
        db.add_all([community, other_community])
        db.flush()
        db.add_all([
            Membership(community_id=community.id, user_id=people["admin"].id, role=MembershipRole.ADMIN),
            Membership(community_id=community.id, user_id=people["owner"].id, role=MembershipRole.ORGANIZER),
            Membership(community_id=community.id, user_id=people["organizer"].id, role=MembershipRole.ORGANIZER),
            Membership(community_id=community.id, user_id=people["member"].id, role=MembershipRole.MEMBER),
            Membership(community_id=community.id, user_id=people["member_two"].id, role=MembershipRole.MEMBER),
            Membership(community_id=community.id, user_id=people["suspended"].id, role=MembershipRole.MEMBER,
                       status=MembershipStatus.SUSPENDED),
            Membership(community_id=community.id, user_id=people["inactive"].id, role=MembershipRole.MEMBER),
            Membership(community_id=community.id, user_id=people["private"].id, role=MembershipRole.MEMBER),
            Membership(community_id=other_community.id, user_id=people["outsider"].id,
                       role=MembershipRole.ORGANIZER),
        ])
        now = datetime.now(UTC)
        event = Event(community_id=community.id, organizer_id=people["owner"].id, title="Owned Event",
                      slug="lp-owned-event", description="Description", category="community",
                      starts_at=now, ends_at=now + timedelta(hours=2), location_type=LocationType.ONLINE)
        other_event = Event(community_id=other_community.id, organizer_id=people["outsider"].id,
                            title="Foreign Event", slug="lp-foreign-event", description="Description",
                            category="community", starts_at=now, ends_at=now + timedelta(hours=2),
                            location_type=LocationType.ONLINE)
        db.add_all([event, other_event])
        db.flush()
        attendance = Attendance(event_id=event.id, user_id=people["member"].id,
                                status=AttendanceStatus.CHECKED_IN, flagged_for_review=True,
                                review_reason="Location confidence below threshold")
        db.add(attendance)
        db.commit()
        ids = {"community": community.id, "other_community": other_community.id, "event": event.id,
               "other_event": other_event.id, "attendance": attendance.id,
               **{name: person.id for name, person in people.items()}}

    app = create_app()

    def override():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override
    return engine, TestClient(app), ids, sessions


def headers(user_id):
    return {"Authorization": f"Bearer {create_access_token(user_id, 'participant')}"}


def staff_row(sessions, event_id, user_id):
    with sessions() as db:
        return db.query(EventStaff).filter_by(event_id=event_id, user_id=user_id).one()


def give_staff(sessions, event_id, user_id, role=EventStaffRole.ATTENDANCE_VERIFIER):
    """Appoint staff directly, for tests whose subject is what staff may then do."""
    with sessions() as db:
        db.add(EventStaff(event_id=event_id, user_id=user_id, role=role, is_active=True))
        db.commit()


def make_task(sessions, community_id, creator_id, title, **overrides):
    with sessions() as db:
        task = Task(community_id=community_id, created_by_id=creator_id, title=title,
                    description="Description", **overrides)
        db.add(task)
        db.commit()
        return task.id


def make_submitted_assignment(sessions, task_id, assignee_id, assigner_id):
    with sessions() as db:
        assignment = TaskAssignment(task_id=task_id, assignee_id=assignee_id, assigned_by_id=assigner_id,
                                    status=TaskAssignmentStatus.SUBMITTED)
        db.add(assignment)
        db.flush()
        db.add(TaskSubmission(assignment_id=assignment.id, evidence_text="Proof of participation",
                              submitted_at=datetime.now(UTC)))
        db.commit()
        return assignment.id


# ── Member lookup (1-10) ──────────────────────────────────────────────────────────────────────


def test_organizer_cannot_list_the_full_member_directory(tmp_path):
    """The directory is a bulk export of personal data; operational delivery never needs it."""
    engine, client, ids, _sessions = setup(tmp_path)
    response = client.get(f"{API}/communities/{ids['community']}/members", headers=headers(ids["organizer"]))
    assert response.status_code == 403
    assert client.get(f"{API}/communities/{ids['community']}/members", headers=headers(ids["member"])).status_code == 403
    assert client.get(f"{API}/communities/{ids['community']}/members", headers=headers(ids["outsider"])).status_code == 403
    engine.dispose()


def test_admin_still_lists_the_directory_with_contact_details(tmp_path):
    engine, client, ids, _sessions = setup(tmp_path)
    response = client.get(f"{API}/communities/{ids['community']}/members", headers=headers(ids["admin"]))
    assert response.status_code == 200
    by_user = {item["user_id"]: item for item in response.json()["members"]}
    assert by_user[str(ids["member"])]["email"] == "member@example.com"
    # The Admin view keeps non-active memberships visible so suspended members can be restored.
    assert by_user[str(ids["suspended"])]["status"] == "suspended"
    engine.dispose()


def test_member_search_requires_a_real_query(tmp_path):
    engine, client, ids, _sessions = setup(tmp_path)
    base = f"{API}/communities/{ids['community']}/members/search"
    assert client.get(base, headers=headers(ids["organizer"]), params={"q": "M"}).status_code == 422
    assert client.get(base, headers=headers(ids["organizer"])).status_code == 422
    assert client.get(base, headers=headers(ids["organizer"]), params={"q": "Mona"}).status_code == 200
    engine.dispose()


def test_exact_email_search_returns_the_address_it_was_asked_for(tmp_path):
    engine, client, ids, _sessions = setup(tmp_path)
    response = client.get(f"{API}/communities/{ids['community']}/members/search",
                          headers=headers(ids["organizer"]), params={"q": "member@example.com"})
    assert response.status_code == 200
    (match,) = response.json()["members"]
    assert match["user_id"] == str(ids["member"])
    assert match["email"] == "member@example.com"
    engine.dispose()


def test_name_search_never_echoes_an_email_address(tmp_path):
    """A name match must not become a way to harvest addresses one display name at a time."""
    engine, client, ids, _sessions = setup(tmp_path)
    response = client.get(f"{API}/communities/{ids['community']}/members/search",
                          headers=headers(ids["organizer"]), params={"q": "Mona Member"})
    assert response.status_code == 200
    (match,) = [item for item in response.json()["members"] if item["user_id"] == str(ids["member"])]
    assert "email" not in match
    assert match["display_name"] == "Mona Member"
    engine.dispose()


def test_username_search_matches_with_or_without_the_at_sign(tmp_path):
    engine, client, ids, _sessions = setup(tmp_path)
    base = f"{API}/communities/{ids['community']}/members/search"
    exact = client.get(base, headers=headers(ids["organizer"]), params={"q": "lp-owner"})
    assert [item["user_id"] for item in exact.json()["members"]] == [str(ids["owner"])]
    assert "email" not in exact.json()["members"][0]
    # The leading "@" convention users type in mentions is accepted.
    assert client.get(base, headers=headers(ids["organizer"]), params={"q": "@lp-owner"}).json()["members"][0][
        "user_id"] == str(ids["owner"])
    engine.dispose()


def test_member_search_cannot_reach_another_community(tmp_path):
    engine, client, ids, _sessions = setup(tmp_path)
    base = f"{API}/communities/{ids['community']}/members/search"
    # An Organizer of community A searching community B's member by exact address learns nothing,
    # so the endpoint cannot be used to confirm that an unrelated account exists.
    for term in ("outsider@example.com", "Oscar Outsider", "lp-outsider"):
        response = client.get(base, headers=headers(ids["organizer"]), params={"q": term})
        assert response.status_code == 200 and response.json()["members"] == [], term
    # A community the caller does not belong to is not searchable at all, even by a name they know.
    assert client.get(f"{API}/communities/{ids['other_community']}/members/search",
                      headers=headers(ids["organizer"]), params={"q": "lp-outsider"}).status_code == 403
    engine.dispose()


def test_member_search_only_returns_active_memberships_and_live_accounts(tmp_path):
    engine, client, ids, _sessions = setup(tmp_path)
    base = f"{API}/communities/{ids['community']}/members/search"
    assert client.get(base, headers=headers(ids["organizer"]), params={"q": "lp-suspended"}).json()["members"] == []
    assert client.get(base, headers=headers(ids["organizer"]), params={"q": "lp-inactive"}).json()["members"] == []
    assert client.get(base, headers=headers(ids["organizer"]), params={"q": "Ada Admin"}).json()["members"][0][
        "user_id"] == str(ids["admin"])
    engine.dispose()


def test_member_search_result_set_is_capped_without_pagination(tmp_path):
    """A shared name may match many members, but the response can never be paged into a directory."""
    engine, client, ids, sessions = setup(tmp_path)
    with sessions() as db:
        for index in range(25):
            person = User(email=f"capstone-{index}@example.com", password_hash=hash_password("password-password"))
            db.add(person)
            db.flush()
            db.add(Profile(user_id=person.id, username=f"capstone-{index}", display_name="Capstone Volunteer"))
            db.add(Membership(community_id=ids["community"], user_id=person.id, role=MembershipRole.MEMBER))
        db.commit()
    base = f"{API}/communities/{ids['community']}/members/search"
    response = client.get(base, headers=headers(ids["organizer"]), params={"q": "Capstone Volunteer"})
    assert response.status_code == 200
    assert len(response.json()["members"]) == 10
    # No offset parameter exists, so repeating the call cannot walk past the cap.
    assert client.get(base, headers=headers(ids["organizer"]),
                      params={"q": "Capstone Volunteer", "offset": 10}).json()["members"] == response.json()["members"]
    engine.dispose()


def test_member_search_escapes_like_wildcards(tmp_path):
    """A query of ``%%`` must be a literal search, not a directory dump."""
    engine, client, ids, _sessions = setup(tmp_path)
    base = f"{API}/communities/{ids['community']}/members/search"
    for term in ("%%", "__", "%a%"):
        assert client.get(base, headers=headers(ids["organizer"]), params={"q": term}).json()["members"] == [], term
    engine.dispose()


def test_member_search_respects_profile_privacy_and_is_audited(tmp_path):
    engine, client, ids, sessions = setup(tmp_path)
    response = client.get(f"{API}/communities/{ids['community']}/members/search",
                          headers=headers(ids["organizer"]), params={"q": "lp-private"})
    assert response.status_code == 200
    (match,) = response.json()["members"]
    assert match["display_name"] == "Private member" and match["username"] is None
    # The audit trail records that a lookup happened without storing the search term itself.
    with sessions() as db:
        entry = db.query(AuditLog).filter_by(action="community.member_searched").order_by(
            AuditLog.occurred_at.desc()).first()
        assert entry is not None and entry.actor_id == ids["organizer"]
        assert entry.metadata_json["query_kind"] == "name" and "lp-private" not in str(entry.metadata_json)
    engine.dispose()


# ── Attendance verification scope (11-17) ─────────────────────────────────────────────────────


def test_fellow_organizer_cannot_verify_attendance_for_an_event_they_do_not_run(tmp_path):
    engine, client, ids, _sessions = setup(tmp_path)
    response = client.post(
        f"{API}/events/{ids['event']}/attendance/{ids['attendance']}/organizer-review",
        headers=headers(ids["organizer"]), json={"approve": True, "reason": "Looks fine to me"})
    assert response.status_code == 403
    engine.dispose()


def test_event_owner_can_verify_attendance(tmp_path):
    engine, client, ids, _sessions = setup(tmp_path)
    response = client.post(
        f"{API}/events/{ids['event']}/attendance/{ids['attendance']}/organizer-review",
        headers=headers(ids["owner"]), json={"approve": True, "reason": "Checked the venue log"})
    assert response.status_code == 200
    engine.dispose()


def test_community_admin_can_verify_attendance_for_any_event(tmp_path):
    engine, client, ids, _sessions = setup(tmp_path)
    response = client.post(
        f"{API}/events/{ids['event']}/attendance/{ids['attendance']}/organizer-review",
        headers=headers(ids["admin"]), json={"approve": True, "reason": "Escalated review"})
    assert response.status_code == 200
    engine.dispose()


def test_appointed_attendance_verifier_can_verify_attendance(tmp_path):
    engine, client, ids, sessions = setup(tmp_path)
    give_staff(sessions, ids["event"], ids["member_two"], EventStaffRole.ATTENDANCE_VERIFIER)
    response = client.post(
        f"{API}/events/{ids['event']}/attendance/{ids['attendance']}/organizer-review",
        headers=headers(ids["member_two"]), json={"approve": True, "reason": "I was at the door"})
    assert response.status_code == 200
    engine.dispose()


def test_staff_without_the_verifier_role_cannot_verify_attendance(tmp_path):
    """Delegation is one job wide: a check-in scanner is not an attendance reviewer."""
    engine, client, ids, sessions = setup(tmp_path)
    give_staff(sessions, ids["event"], ids["member_two"], EventStaffRole.CHECK_IN)
    response = client.post(
        f"{API}/events/{ids['event']}/attendance/{ids['attendance']}/organizer-review",
        headers=headers(ids["member_two"]), json={"approve": True, "reason": "I was at the door"})
    assert response.status_code == 403
    engine.dispose()


def test_foreign_organizer_cannot_reach_another_communitys_attendance(tmp_path):
    engine, client, ids, _sessions = setup(tmp_path)
    base = f"{API}/events/{ids['event']}/attendance"
    assert client.get(f"{base}/review", headers=headers(ids["outsider"])).status_code == 403
    assert client.get(f"{base}/roster", headers=headers(ids["outsider"])).status_code == 403
    assert client.post(f"{base}/{ids['attendance']}/organizer-review", headers=headers(ids["outsider"]),
                       json={"approve": True, "reason": "Not my community"}).status_code == 403
    engine.dispose()


def test_attendance_review_and_roster_follow_event_ownership(tmp_path):
    engine, client, ids, sessions = setup(tmp_path)
    review = f"{API}/events/{ids['event']}/attendance/review"
    roster = f"{API}/events/{ids['event']}/attendance/roster"
    assert client.get(review, headers=headers(ids["owner"])).status_code == 200
    assert client.get(roster, headers=headers(ids["owner"])).status_code == 200
    assert client.get(review, headers=headers(ids["admin"])).status_code == 200
    assert client.get(review, headers=headers(ids["organizer"])).status_code == 403
    assert client.get(roster, headers=headers(ids["organizer"])).status_code == 403
    assert client.get(review, headers=headers(ids["member"])).status_code == 403
    # An appointed verifier picks up exactly the review surface the ownership rule protects.
    give_staff(sessions, ids["event"], ids["member_two"], EventStaffRole.ATTENDANCE_VERIFIER)
    assert client.get(review, headers=headers(ids["member_two"])).status_code == 200
    engine.dispose()


# ── EventStaff delegation (18-22) ────────────────────────────────────────────────────────────


def test_event_owner_can_appoint_list_and_revoke_staff(tmp_path):
    engine, client, ids, sessions = setup(tmp_path)
    base = f"{API}/events/{ids['event']}/staff"
    created = client.post(base, headers=headers(ids["owner"]),
                          json={"user_id": str(ids["member"]), "role": "attendance_verifier"})
    assert created.status_code == 201
    assert created.json()["role"] == "attendance_verifier" and created.json()["is_active"] is True
    staff_id = created.json()["id"]
    listed = client.get(base, headers=headers(ids["owner"]))
    assert [item["id"] for item in listed.json()] == [staff_id]
    # A staff list is operational data: name and role, never a contact detail.
    assert "email" not in listed.json()[0]
    assert client.delete(f"{base}/{staff_id}", headers=headers(ids["owner"])).status_code == 200
    assert staff_row(sessions, ids["event"], ids["member"]).is_active is False
    assert client.get(base, headers=headers(ids["owner"])).json()[0]["is_active"] is False
    engine.dispose()


def test_community_admin_can_appoint_staff_for_an_organizers_event(tmp_path):
    engine, client, ids, _sessions = setup(tmp_path)
    response = client.post(f"{API}/events/{ids['event']}/staff", headers=headers(ids["admin"]),
                           json={"user_id": str(ids["member"]), "role": "attendance_verifier"})
    assert response.status_code == 201
    assert client.get(f"{API}/events/{ids['event']}/staff", headers=headers(ids["admin"])).status_code == 200
    engine.dispose()


def test_only_the_owner_or_an_admin_may_grant_event_staff(tmp_path):
    """Appointment is deliberately not delegable, or a narrow grant would widen itself."""
    engine, client, ids, _sessions = setup(tmp_path)
    base = f"{API}/events/{ids['event']}/staff"
    payload = {"user_id": str(ids["member"]), "role": "attendance_verifier"}
    assert client.post(base, headers=headers(ids["organizer"]), json=payload).status_code == 403
    assert client.post(base, headers=headers(ids["member"]), json=payload).status_code == 403
    assert client.get(base, headers=headers(ids["organizer"])).status_code == 403
    assert client.post(base, headers=headers(ids["owner"]), json=payload).status_code == 201
    # An appointed verifier inherits the job, not the authority to hand it to somebody else.
    assert client.post(base, headers=headers(ids["member"]),
                       json={"user_id": str(ids["member_two"]), "role": "attendance_verifier"}).status_code == 403
    assert client.delete(f"{base}/{ids['member']}", headers=headers(ids["member"])).status_code == 403
    engine.dispose()


def test_staff_assignment_rejects_unknown_roles_and_ineligible_people(tmp_path):
    engine, client, ids, _sessions = setup(tmp_path)
    base = f"{API}/events/{ids['event']}/staff"
    assert client.post(base, headers=headers(ids["owner"]),
                       json={"user_id": str(ids["member"]), "role": "community_admin"}).status_code == 422
    # Not a member of this community at all.
    assert client.post(base, headers=headers(ids["owner"]),
                       json={"user_id": str(ids["outsider"]), "role": "check_in"}).status_code == 404
    # A membership that exists but is not active.
    assert client.post(base, headers=headers(ids["owner"]),
                       json={"user_id": str(ids["suspended"]), "role": "check_in"}).status_code == 404
    # An active membership belonging to a deactivated account.
    assert client.post(base, headers=headers(ids["owner"]),
                       json={"user_id": str(ids["inactive"]), "role": "check_in"}).status_code == 404
    assert client.get(base, headers=headers(ids["owner"])).json() == []
    engine.dispose()


def test_staff_management_is_tenant_scoped_and_audited(tmp_path):
    engine, client, ids, sessions = setup(tmp_path)
    base = f"{API}/events/{ids['event']}/staff"
    # An organizer of the other community cannot manage staff on this event.
    assert client.get(base, headers=headers(ids["outsider"])).status_code == 403
    assert client.post(base, headers=headers(ids["outsider"]),
                       json={"user_id": str(ids["member"]), "role": "check_in"}).status_code == 403
    created = client.post(base, headers=headers(ids["owner"]),
                          json={"user_id": str(ids["member"]), "role": "check_in"})
    staff_id = created.json()["id"]
    # A staff id from another event reads as absent rather than forbidden, so ids cannot be probed.
    foreign = client.post(f"{API}/events/{ids['other_event']}/staff", headers=headers(ids["outsider"]),
                          json={"user_id": str(ids["outsider"]), "role": "check_in"})
    assert foreign.status_code == 201
    assert client.delete(f"{base}/{foreign.json()['id']}", headers=headers(ids["owner"])).status_code == 404
    # Re-appointing the same person updates in place instead of duplicating.
    updated = client.post(base, headers=headers(ids["owner"]),
                          json={"user_id": str(ids["member"]), "role": "ticket_validator"})
    assert updated.status_code == 201 and updated.json()["id"] == staff_id
    assert updated.json()["role"] == "ticket_validator"
    assert client.delete(f"{base}/{staff_id}", headers=headers(ids["owner"])).status_code == 200
    with sessions() as db:
        actions = {row.action for row in db.query(AuditLog).filter(AuditLog.action.like("event.staff.%"))}
        assert actions == {"event.staff.assigned", "event.staff.updated", "event.staff.revoked"}
    engine.dispose()


# ── Task management ownership (23-30) ────────────────────────────────────────────────────────


def test_any_organizer_may_still_create_a_task(tmp_path):
    engine, client, ids, _sessions = setup(tmp_path)
    response = client.post(f"{API}/communities/{ids['community']}/tasks", headers=headers(ids["organizer"]),
                           json={"title": "Community clean-up", "description": "Join the clean-up drive"})
    assert response.status_code == 201
    assert client.post(f"{API}/communities/{ids['community']}/tasks", headers=headers(ids["member"]),
                       json={"title": "Nope", "description": "Participants do not create tasks"}).status_code == 403
    engine.dispose()


def test_organizer_cannot_edit_a_colleagues_task(tmp_path):
    engine, client, ids, sessions = setup(tmp_path)
    task_id = make_task(sessions, ids["community"], ids["owner"], "Owner task")
    response = client.patch(f"{API}/tasks/{task_id}", headers=headers(ids["organizer"]),
                            json={"title": "Renamed by a bystander"})
    assert response.status_code == 403
    assert client.patch(f"{API}/tasks/{task_id}", headers=headers(ids["member"]),
                        json={"title": "Renamed by a participant"}).status_code == 403
    engine.dispose()


def test_organizer_can_edit_and_admin_can_edit_any_task(tmp_path):
    engine, client, ids, sessions = setup(tmp_path)
    own_task = make_task(sessions, ids["community"], ids["organizer"], "Organizer task")
    owner_task = make_task(sessions, ids["community"], ids["owner"], "Owner task")
    assert client.patch(f"{API}/tasks/{own_task}", headers=headers(ids["organizer"]),
                        json={"title": "Organizer task, revised"}).status_code == 200
    assert client.patch(f"{API}/tasks/{owner_task}", headers=headers(ids["admin"]),
                        json={"title": "Owner task, reviewed by Admin"}).status_code == 200
    engine.dispose()


def test_organizer_cannot_assign_a_colleagues_task(tmp_path):
    engine, client, ids, sessions = setup(tmp_path)
    owner_task = make_task(sessions, ids["community"], ids["owner"], "Owner task")
    own_task = make_task(sessions, ids["community"], ids["organizer"], "Organizer task")
    assert client.post(f"{API}/tasks/{owner_task}/assignments", headers=headers(ids["organizer"]),
                       json={"assignee_id": str(ids["member"])}).status_code == 403
    assert client.post(f"{API}/tasks/{own_task}/assignments", headers=headers(ids["organizer"]),
                       json={"assignee_id": str(ids["member"])}).status_code == 201
    assert client.post(f"{API}/tasks/{own_task}/assignments", headers=headers(ids["admin"]),
                       json={"assignee_id": str(ids["member_two"])}).status_code == 201
    engine.dispose()


def test_organizer_cannot_bulk_assign_a_colleagues_task(tmp_path):
    engine, client, ids, sessions = setup(tmp_path)
    owner_task = make_task(sessions, ids["community"], ids["owner"], "Owner task")
    body = {"selected_ids": [str(ids["member"]), str(ids["member_two"])]}
    assert client.post(f"{API}/tasks/{owner_task}/assignment-candidates", headers=headers(ids["organizer"]),
                       json={"all_members": True}).status_code == 403
    assert client.post(f"{API}/tasks/{owner_task}/assignments/bulk", headers=headers(ids["organizer"]),
                       json=body).status_code == 403
    engine.dispose()


def test_organizer_verification_queue_only_covers_their_own_tasks(tmp_path):
    engine, client, ids, sessions = setup(tmp_path)
    owner_task = make_task(sessions, ids["community"], ids["owner"], "Owner task")
    organizer_task = make_task(sessions, ids["community"], ids["organizer"], "Organizer task")
    make_submitted_assignment(sessions, owner_task, ids["member"], ids["owner"])
    make_submitted_assignment(sessions, organizer_task, ids["member_two"], ids["organizer"])
    queue = f"{API}/communities/{ids['community']}/task-verification-queue"
    mine = client.get(queue, headers=headers(ids["organizer"]))
    assert mine.status_code == 200
    assert [item["task_id"] for item in mine.json()] == [str(organizer_task)]
    theirs = client.get(queue, headers=headers(ids["owner"]))
    assert [item["task_id"] for item in theirs.json()] == [str(owner_task)]
    engine.dispose()


def test_admin_verification_queue_covers_every_community_task(tmp_path):
    engine, client, ids, sessions = setup(tmp_path)
    owner_task = make_task(sessions, ids["community"], ids["owner"], "Owner task")
    organizer_task = make_task(sessions, ids["community"], ids["organizer"], "Organizer task")
    make_submitted_assignment(sessions, owner_task, ids["member"], ids["owner"])
    make_submitted_assignment(sessions, organizer_task, ids["member_two"], ids["organizer"])
    response = client.get(f"{API}/communities/{ids['community']}/task-verification-queue",
                          headers=headers(ids["admin"]))
    assert sorted(item["task_id"] for item in response.json()) == sorted([str(owner_task), str(organizer_task)])
    engine.dispose()


def test_organizer_cannot_verify_another_organizers_submission(tmp_path):
    engine, client, ids, sessions = setup(tmp_path)
    owner_task = make_task(sessions, ids["community"], ids["owner"], "Owner task")
    assignment_id = make_submitted_assignment(sessions, owner_task, ids["member"], ids["owner"])
    verify = f"{API}/task-assignments/{assignment_id}/verify"
    assert client.post(verify, headers=headers(ids["organizer"]),
                       json={"approve": True, "reason": "Not my task"}).status_code == 403
    assert client.post(verify, headers=headers(ids["admin"]),
                       json={"approve": True, "reason": "Admin review"}).status_code == 200
    engine.dispose()


def test_management_task_views_are_owner_scoped_for_organizers(tmp_path):
    engine, client, ids, sessions = setup(tmp_path)
    owner_task = make_task(sessions, ids["community"], ids["owner"], "Owner task")
    organizer_task = make_task(sessions, ids["community"], ids["organizer"], "Organizer task")
    listing = f"{API}/communities/{ids['community']}/tasks"
    mine = client.get(listing, headers=headers(ids["organizer"]), params={"management": True})
    assert {item["id"] for item in mine.json()} == {str(organizer_task)}
    theirs = client.get(listing, headers=headers(ids["admin"]), params={"management": True})
    assert {item["id"] for item in theirs.json()} == {str(owner_task), str(organizer_task)}
    assert client.get(f"{API}/tasks/{owner_task}", headers=headers(ids["organizer"]),
                      params={"management": True}).status_code == 403
    assert client.get(f"{API}/tasks/{organizer_task}", headers=headers(ids["organizer"]),
                      params={"management": True}).status_code == 200
    assert client.get(f"{API}/tasks/{owner_task}", headers=headers(ids["admin"]),
                      params={"management": True}).status_code == 200
    # Participants keep their own redacted read of any task in the community.
    assert client.get(f"{API}/tasks/{owner_task}", headers=headers(ids["member"])).status_code == 200
    engine.dispose()


# ── Follow-up helpers ────────────────────────────────────────────────────────────────────────


def set_staff(sessions, event_id, user_id, role, *, is_active=True):
    """Upsert one staff row. ``event_staff`` holds at most one row per (event, user)."""
    with sessions() as db:
        row = db.query(EventStaff).filter_by(event_id=event_id, user_id=user_id).one_or_none()
        if row is None:
            db.add(EventStaff(event_id=event_id, user_id=user_id, role=role, is_active=is_active))
        else:
            row.role, row.is_active = role, is_active
        db.commit()


def make_ticket(sessions, event_id, attendee_id, token):
    """One active, claimed ticket on its own ticket type, ready to be scanned."""
    with sessions() as db:
        ticket_type = TicketType(event_id=event_id, name=f"Admission {token}", quantity=10)
        db.add(ticket_type)
        db.flush()
        ticket = Ticket(public_id=token[:32], qr_token=token, event_id=event_id,
                        ticket_type_id=ticket_type.id, attendee_id=attendee_id,
                        status=TicketStatus.ACTIVE, assignment_state=TicketAssignmentState.CLAIMED)
        db.add(ticket)
        db.commit()
        return ticket.id


# ``TicketValidationRequest.qr_token`` is ``Field(min_length=32, max_length=128)``. A shorter token
# is refused 422 by request validation, before the route body runs at all — so a test token under
# this floor would assert nothing about authorization and everything about Pydantic.
QR_TOKEN_MIN_LENGTH = 32


def qr_token(label: str) -> str:
    """A scan token the validation route actually accepts, distinct per label."""
    token = f"qr-{label}".ljust(QR_TOKEN_MIN_LENGTH, "0")
    assert QR_TOKEN_MIN_LENGTH <= len(token) <= 128, label
    return token


def scan(client, ids, token, user_id):
    return client.post(f"{API}/events/{ids['event']}/tickets/validate",
                       headers=headers(user_id), json={"qr_token": token})


# ── Ticket validation reachability (31-35) ───────────────────────────────────────────────────


def test_appointed_member_staff_can_validate_a_ticket(tmp_path):
    """The regression: a plain member appointed to the door was refused by the community floor.

    Ticket scanning is delivered through per-event delegation, so the gate must be event staff
    authority rather than an Organizer membership — otherwise the delegation is unusable for
    exactly the people it exists to appoint.
    """
    engine, client, ids, sessions = setup(tmp_path)
    set_staff(sessions, ids["event"], ids["member_two"], EventStaffRole.CHECK_IN)
    token = qr_token("door-scan")
    make_ticket(sessions, ids["event"], ids["member"], token)
    response = scan(client, ids, token, ids["member_two"])
    assert response.status_code == 200
    assert response.json()["result"] == "valid"
    engine.dispose()


def test_every_door_role_can_validate_a_ticket(tmp_path):
    """All four staff roles may admit an attendee; that is what the admission group means."""
    engine, client, ids, sessions = setup(tmp_path)
    for index, role in enumerate((EventStaffRole.MANAGER, EventStaffRole.CHECK_IN,
                                  EventStaffRole.TICKET_VALIDATOR, EventStaffRole.ATTENDANCE_VERIFIER)):
        set_staff(sessions, ids["event"], ids["member_two"], role)
        token = qr_token(f"door-role-{index}")
        make_ticket(sessions, ids["event"], ids["member"], token)
        response = scan(client, ids, token, ids["member_two"])
        assert response.status_code == 200 and response.json()["result"] == "valid", role
    engine.dispose()


def test_ticket_validation_authority_matrix(tmp_path):
    engine, client, ids, sessions = setup(tmp_path)
    token = qr_token("matrix")
    make_ticket(sessions, ids["event"], ids["member"], token)
    # A fellow Organizer of the community is not automatically door staff for somebody else's event.
    assert scan(client, ids, token, ids["organizer"]).status_code == 403
    # Nor is the ticket's own holder, or an Organizer of an unrelated community.
    assert scan(client, ids, token, ids["member"]).status_code == 403
    assert scan(client, ids, token, ids["outsider"]).status_code == 403
    allowed = scan(client, ids, token, ids["owner"])
    assert allowed.status_code == 200 and allowed.json()["result"] == "valid"
    # The refusals above never reached the ticket, and an Admin's authority is checked against the
    # ticket's own state rather than refused outright.
    assert scan(client, ids, token, ids["admin"]).json()["result"] == "already_used"
    engine.dispose()


def test_revoked_or_inactive_event_staff_cannot_validate_tickets(tmp_path):
    engine, client, ids, sessions = setup(tmp_path)
    token = qr_token("revoked")
    make_ticket(sessions, ids["event"], ids["member"], token)
    set_staff(sessions, ids["event"], ids["member_two"], EventStaffRole.CHECK_IN, is_active=False)
    assert scan(client, ids, token, ids["member_two"]).status_code == 403
    # The same row re-activated works, so the refusal above is the ``is_active`` flag and nothing else.
    set_staff(sessions, ids["event"], ids["member_two"], EventStaffRole.CHECK_IN)
    assert scan(client, ids, token, ids["member_two"]).status_code == 200
    engine.dispose()


def test_ticket_validation_still_refuses_a_suspended_event(tmp_path):
    """Event lifecycle and tenant checks are untouched by the authority change."""
    engine, client, ids, sessions = setup(tmp_path)
    set_staff(sessions, ids["event"], ids["member_two"], EventStaffRole.CHECK_IN)
    with sessions() as db:
        db.get(Event, ids["event"]).is_suspended = True
        db.commit()
    token = qr_token("suspended")
    assert scan(client, ids, token, ids["member_two"]).status_code == 403
    assert scan(client, ids, token, ids["owner"]).status_code == 403
    engine.dispose()


# ── Event analytics scope (36-38) ────────────────────────────────────────────────────────────


def test_event_analytics_follow_event_scope(tmp_path):
    engine, client, ids, _sessions = setup(tmp_path)
    url = f"{API}/events/{ids['event']}/analytics"
    assert client.get(url, headers=headers(ids["owner"])).status_code == 200
    # A community Admin oversees every event in the community and keeps this.
    assert client.get(url, headers=headers(ids["admin"])).status_code == 200
    # A fellow Organizer does not, and neither does a participant or another community's Organizer.
    assert client.get(url, headers=headers(ids["organizer"])).status_code == 403
    assert client.get(url, headers=headers(ids["member"])).status_code == 403
    assert client.get(url, headers=headers(ids["outsider"])).status_code == 403
    engine.dispose()


def test_event_analytics_reach_delegated_staff_only_in_the_manager_role(tmp_path):
    """The figures include contributions and Impact points, so reporting stays with the role that runs the event."""
    engine, client, ids, sessions = setup(tmp_path)
    url = f"{API}/events/{ids['event']}/analytics"
    for role in (EventStaffRole.CHECK_IN, EventStaffRole.TICKET_VALIDATOR,
                 EventStaffRole.ATTENDANCE_VERIFIER):
        set_staff(sessions, ids["event"], ids["member_two"], role)
        assert client.get(url, headers=headers(ids["member_two"])).status_code == 403, role
    set_staff(sessions, ids["event"], ids["member_two"], EventStaffRole.MANAGER)
    assert client.get(url, headers=headers(ids["member_two"])).status_code == 200
    engine.dispose()


def test_community_analytics_remain_admin_only(tmp_path):
    """Narrowing the event view must not be mistaken for narrowing the community view."""
    engine, client, ids, _sessions = setup(tmp_path)
    url = f"{API}/communities/{ids['community']}/analytics"
    assert client.get(url, headers=headers(ids["admin"])).status_code == 200
    assert client.get(url, headers=headers(ids["organizer"])).status_code == 403
    assert client.get(url, headers=headers(ids["outsider"])).status_code == 403
    engine.dispose()


# ── EventStaff role semantics (39-41) ────────────────────────────────────────────────────────


def test_event_configuration_is_management_only(tmp_path):
    """Defining or reading what an event gives away is running it, not working its door."""
    engine, client, ids, sessions = setup(tmp_path)
    entitlements = f"{API}/events/{ids['event']}/entitlements"
    assert client.get(entitlements, headers=headers(ids["owner"])).status_code == 200
    for role in (EventStaffRole.CHECK_IN, EventStaffRole.TICKET_VALIDATOR,
                 EventStaffRole.ATTENDANCE_VERIFIER):
        set_staff(sessions, ids["event"], ids["member_two"], role)
        assert client.get(entitlements, headers=headers(ids["member_two"])).status_code == 403, role
    set_staff(sessions, ids["event"], ids["member_two"], EventStaffRole.MANAGER)
    assert client.get(entitlements, headers=headers(ids["member_two"])).status_code == 200
    engine.dispose()


def test_redemption_history_is_management_only(tmp_path):
    """It names attendees and what they took, which is oversight rather than door work."""
    engine, client, ids, sessions = setup(tmp_path)
    history = f"{API}/events/{ids['event']}/redemptions"
    assert client.get(history, headers=headers(ids["owner"])).status_code == 200
    set_staff(sessions, ids["event"], ids["member_two"], EventStaffRole.CHECK_IN)
    assert client.get(history, headers=headers(ids["member_two"])).status_code == 403
    set_staff(sessions, ids["event"], ids["member_two"], EventStaffRole.MANAGER)
    assert client.get(history, headers=headers(ids["member_two"])).status_code == 200
    engine.dispose()


def test_benefit_redemption_is_open_to_every_door_role(tmp_path):
    """Handing over a perk is admission: refused callers get 403, admitted ones reach the check.

    The exact 404 is load-bearing. ``validate_redemption`` scopes its credential lookup by the
    event *id*, so a route that hands it the ORM row instead fails inside the query and answers
    500 — which asserting a bare status code would not have caught.
    """
    engine, client, ids, sessions = setup(tmp_path)
    url = f"{API}/events/{ids['event']}/redemptions/validate"
    # A well-formed credential that belongs to nobody: the point is where the request is refused.
    body = {"code": "ZZZZ"}
    assert client.post(url, headers=headers(ids["organizer"]), json=body).status_code == 403
    assert client.post(url, headers=headers(ids["member"]), json=body).status_code == 403
    # The owner and every admission role get past authority to the unknown-credential answer.
    assert client.post(url, headers=headers(ids["owner"]), json=body).status_code == 404
    for role in (EventStaffRole.CHECK_IN, EventStaffRole.TICKET_VALIDATOR,
                 EventStaffRole.ATTENDANCE_VERIFIER, EventStaffRole.MANAGER):
        set_staff(sessions, ids["event"], ids["member_two"], role)
        assert client.post(url, headers=headers(ids["member_two"]), json=body).status_code == 404, role
    engine.dispose()


def test_redemption_route_passes_an_event_id_not_an_event_row(tmp_path):
    """Regression: the route resolved the event and then handed the row to a UUID parameter.

    Authority runs first, so a caller who is refused gets 403 whether or not the parameter is
    right; the mismatch only shows for an *authorized* caller, where the credential lookup is the
    first thing to touch the value. Both halves are asserted so that neither a broken parameter nor
    a removed authorization check can pass this test.
    """
    engine, client, ids, _sessions = setup(tmp_path)
    url = f"{API}/events/{ids['event']}/redemptions/validate"
    body = {"code": "ZZZZ"}
    assert client.post(url, headers=headers(ids["outsider"]), json=body).status_code == 403
    denied = client.post(url, headers=headers(ids["owner"]), json=body)
    assert denied.status_code == 404
    assert denied.json()["detail"] == "Invalid or unknown redemption credential"
    engine.dispose()


def test_a_short_scan_token_is_refused_before_authorization(tmp_path):
    """Pins the request-schema floor that :func:`qr_token` pads to.

    Request validation runs before the route body, so a token under the floor answers 422 for
    every caller — including ones the authority rules would allow. Recording that here means a
    future short token in this file fails as an obvious fixture bug rather than being mistaken for
    an authorization result.
    """
    engine, client, ids, sessions = setup(tmp_path)
    set_staff(sessions, ids["event"], ids["member_two"], EventStaffRole.CHECK_IN)
    short = "too-short-to-scan"
    assert len(short) < QR_TOKEN_MIN_LENGTH
    assert scan(client, ids, short, ids["member_two"]).status_code == 422
    # The same caller past request validation reaches the service, which reports an unknown token.
    accepted = scan(client, ids, qr_token("floor"), ids["member_two"])
    assert accepted.status_code == 200 and accepted.json()["result"] == "invalid"
    engine.dispose()
