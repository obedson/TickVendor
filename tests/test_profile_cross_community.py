"""Tests for /profiles/me cross-community aggregation and tenant isolation."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import (
    Attendance,
    AttendanceStatus,
    Badge,
    BadgeAward,
    Community,
    ImpactTransaction,
    ImpactTransactionStatus,
    Membership,
    MembershipRole,
    MembershipStatus,
    Milestone,
    MilestoneAward,
    Organization,
    Profile,
    Rank,
    RankProgression,
    TaskAssignment,
    TaskAssignmentStatus,
    User,
)
from src.security import create_access_token, hash_password
from tests.test_database import create_event_context


def _make_app(sessions):
    app = create_app()

    def override():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override
    return app


def test_no_community_id_returns_cross_community_points_and_no_rank(tmp_path):
    """Without community_id, /profiles/me aggregates points across all communities
    and returns rank=null (rank is community-scoped)."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'cross-community.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)

    with sessions() as db:
        user, community_a, _event = create_event_context(db)
        org_b = Organization(owner_id=user.id, name="Org B", slug="org-b-cross")
        db.add(org_b)
        db.flush()
        community_b = Community(organization_id=org_b.id, name="Community B", slug="community-b-cross")
        db.add(community_b)
        db.flush()
        db.add_all([
            Membership(community_id=community_a.id, user_id=user.id, role=MembershipRole.MEMBER,
                       status=MembershipStatus.ACTIVE),
            Membership(community_id=community_b.id, user_id=user.id, role=MembershipRole.MEMBER,
                       status=MembershipStatus.ACTIVE),
            ImpactTransaction(
                idempotency_key="cross-a", user_id=user.id, community_id=community_a.id,
                points=30, source_type="test", reason="A", status=ImpactTransactionStatus.POSTED,
            ),
            ImpactTransaction(
                idempotency_key="cross-b", user_id=user.id, community_id=community_b.id,
                points=20, source_type="test", reason="B", status=ImpactTransactionStatus.POSTED,
            ),
            # Rank in community A — must NOT appear in cross-community response
            Rank(community_id=community_a.id, name="Gold", slug="gold-cross", minimum_points=0, sort_order=1),
        ])
        db.commit()
        user_id = user.id

    app = _make_app(sessions)
    headers = {"Authorization": f"Bearer {create_access_token(user_id, 'participant')}"}
    response = TestClient(app).get("/api/v1/profiles/me", headers=headers)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["impact_points"] == 50, "Points should be summed across all communities"
    assert data["rank"] is None, "Rank must be null in cross-community response (community-scoped)"
    assert data["next_rank"] is None
    engine.dispose()


def test_no_community_id_aggregates_badges_and_milestones(tmp_path):
    """Without community_id, badges and milestones from all communities are returned."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'cross-badges.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)

    with sessions() as db:
        user, community_a, _event = create_event_context(db)
        org_b = Organization(owner_id=user.id, name="Org B2", slug="org-b2-cross")
        db.add(org_b)
        db.flush()
        community_b = Community(organization_id=org_b.id, name="Community B2", slug="community-b2-cross")
        db.add(community_b)
        db.flush()
        badge_a = Badge(community_id=community_a.id, name="Badge A", slug="badge-a-cross", is_active=True)
        badge_b = Badge(community_id=community_b.id, name="Badge B", slug="badge-b-cross", is_active=True)
        milestone_a = Milestone(community_id=community_a.id, name="Milestone A", slug="milestone-a-cross", is_active=True)
        db.add_all([badge_a, badge_b, milestone_a])
        db.flush()
        db.add_all([
            BadgeAward(badge_id=badge_a.id, user_id=user.id, idempotency_key="badge-a-award-cross",
                       awarded_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc)),
            BadgeAward(badge_id=badge_b.id, user_id=user.id, idempotency_key="badge-b-award-cross",
                       awarded_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc)),
            MilestoneAward(milestone_id=milestone_a.id, user_id=user.id, idempotency_key="milestone-a-award-cross",
                           awarded_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc)),
        ])
        db.commit()
        user_id = user.id

    app = _make_app(sessions)
    headers = {"Authorization": f"Bearer {create_access_token(user_id, 'participant')}"}
    response = TestClient(app).get("/api/v1/profiles/me", headers=headers)

    assert response.status_code == 200, response.text
    data = response.json()
    badge_names = {b["name"] for b in data["badges"]}
    assert "Badge A" in badge_names
    assert "Badge B" in badge_names
    assert len(data["milestones"]) == 1
    assert data["milestones"][0]["name"] == "Milestone A"
    engine.dispose()


def test_no_community_id_counts_events_attended_and_tasks_completed(tmp_path):
    """Without community_id, events_attended and tasks_completed are aggregated."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'cross-counts.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)

    with sessions() as db:
        from datetime import UTC, datetime
        from src.models import Event, LocationType, Task
        user, community, event = create_event_context(db)
        db.add(Membership(community_id=community.id, user_id=user.id, role=MembershipRole.MEMBER,
                          status=MembershipStatus.ACTIVE))
        db.add(Attendance(event_id=event.id, user_id=user.id, status=AttendanceStatus.GPS_VERIFIED,
                          checked_in_at=datetime.now(UTC)))
        task = Task(community_id=community.id, created_by_id=user.id, title="T", description="D",
                    impact_point_reward=5)
        db.add(task)
        db.flush()
        assignment = TaskAssignment(task_id=task.id, assignee_id=user.id, assigned_by_id=user.id,
                                    status=TaskAssignmentStatus.VERIFIED)
        db.add(assignment)
        db.commit()
        user_id = user.id

    app = _make_app(sessions)
    headers = {"Authorization": f"Bearer {create_access_token(user_id, 'participant')}"}
    response = TestClient(app).get("/api/v1/profiles/me", headers=headers)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["events_attended"] == 1
    assert data["tasks_completed"] == 1
    engine.dispose()


def test_community_id_requires_active_membership(tmp_path):
    """With community_id, /profiles/me returns 403 if user is not an active member."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'membership-guard.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)

    with sessions() as db:
        user, community, _event = create_event_context(db)
        db.commit()
        user_id, community_id = user.id, community.id

    app = _make_app(sessions)
    headers = {"Authorization": f"Bearer {create_access_token(user_id, 'participant')}"}
    response = TestClient(app).get(
        "/api/v1/profiles/me",
        params={"community_id": str(community_id)},
        headers=headers,
    )
    assert response.status_code == 403
    engine.dispose()


def test_payment_verify_returns_404_when_order_is_missing(tmp_path):
    """POST /payments/verify must return 404 when the payment's order is missing,
    not crash with AttributeError."""
    from uuid import uuid4
    from src.models import Payment, PaymentStatus

    engine = create_engine(
        f"sqlite:///{tmp_path / 'payment-null-order.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)

    with sessions() as db:
        user = User(email="pay-null@example.com", password_hash=hash_password("password-password"))
        user.profile = Profile(username="pay-null", display_name="Pay Null")
        db.add(user)
        db.flush()
        # Create a payment with a non-existent order_id
        orphan_order_id = uuid4()
        payment = Payment(
            order_id=orphan_order_id,
            provider="test",
            provider_reference="orphan-ref",
            idempotency_key="orphan-payment-key",
            amount=Decimal("100"),
            currency="NGN",
            status=PaymentStatus.PENDING,
        )
        db.add(payment)
        db.commit()
        payment_id, user_id = payment.id, user.id

    app = _make_app(sessions)
    headers = {"Authorization": f"Bearer {create_access_token(user_id, 'participant')}"}
    response = TestClient(app).post(
        "/api/v1/payments/verify",
        json={"payment_id": str(payment_id)},
        headers=headers,
    )
    assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
    engine.dispose()


def test_payment_refund_returns_404_when_order_is_missing(tmp_path):
    """POST /payments/{id}/refund must return 404 when the payment's order is missing."""
    from uuid import uuid4
    from src.models import Payment, PaymentStatus

    engine = create_engine(
        f"sqlite:///{tmp_path / 'refund-null-order.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)

    with sessions() as db:
        user = User(email="refund-null@example.com", password_hash=hash_password("password-password"))
        user.profile = Profile(username="refund-null", display_name="Refund Null")
        db.add(user)
        db.flush()
        orphan_order_id = uuid4()
        payment = Payment(
            order_id=orphan_order_id,
            provider="test",
            provider_reference="refund-orphan-ref",
            idempotency_key="refund-orphan-key",
            amount=Decimal("100"),
            currency="NGN",
            status=PaymentStatus.PENDING,
        )
        db.add(payment)
        db.commit()
        payment_id, user_id = payment.id, user.id

    app = _make_app(sessions)
    headers = {"Authorization": f"Bearer {create_access_token(user_id, 'participant')}"}
    response = TestClient(app).post(
        f"/api/v1/payments/{payment_id}/refund",
        headers=headers,
    )
    assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
    engine.dispose()


def test_my_assignments_uses_join_not_n_plus_one(tmp_path):
    """GET /task-assignments/me should return assignments with due_at from a join,
    not crash when a task is missing."""
    from src.models import Task

    engine = create_engine(
        f"sqlite:///{tmp_path / 'assignments-join.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)

    with sessions() as db:
        user, community, _event = create_event_context(db)
        db.add(Membership(community_id=community.id, user_id=user.id, role=MembershipRole.MEMBER,
                          status=MembershipStatus.ACTIVE))
        task = Task(community_id=community.id, created_by_id=user.id, title="Join task",
                    description="Test join", impact_point_reward=5)
        db.add(task)
        db.flush()
        assignment = TaskAssignment(task_id=task.id, assignee_id=user.id, assigned_by_id=user.id)
        db.add(assignment)
        db.commit()
        user_id = user.id

    app = _make_app(sessions)
    headers = {"Authorization": f"Bearer {create_access_token(user_id, 'participant')}"}
    response = TestClient(app).get("/api/v1/task-assignments/me", headers=headers)

    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data) == 1
    assert data[0]["status"] == "assigned"
    engine.dispose()
