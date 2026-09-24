"""Focused tests for task type validation, evidence handling, and tenant isolation.

NOTE: These tests cannot run in this environment (pytest missing / npm registry 403).
They are written carefully against the actual service/API contracts and marked NOT VERIFIED.
"""

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import src.models  # noqa: F401
from src.database import Base
from src.models import (
    Membership,
    MembershipRole,
    MembershipStatus,
    TaskType,
    User,
)
from src.services.task import (
    assign_task,
    create_task,
    submit_task,
)
from tests.test_database import create_event_context


def _make_session(tmp_path, name="task_type.db"):
    engine = create_engine(
        f"sqlite:///{tmp_path / name}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    return sessions, engine


def _setup_community(db: Session):
    """Create organizer + member in a community."""
    organizer, community, event = create_event_context(db)
    member = User(email=f"member-{id(db)}@example.com", password_hash="hash")
    db.add(member)
    db.flush()
    db.add_all([
        Membership(community_id=community.id, user_id=organizer.id, role=MembershipRole.ORGANIZER, status=MembershipStatus.ACTIVE),
        Membership(community_id=community.id, user_id=member.id, role=MembershipRole.MEMBER, status=MembershipStatus.ACTIVE),
    ])
    db.commit()
    return organizer, member, community, event


# ── Task type validation ──────────────────────────────────────────────────────

def test_create_general_task_succeeds(tmp_path):
    """General task with no config creates successfully."""
    sessions, engine = _make_session(tmp_path, "general.db")
    with sessions() as db:
        organizer, _member, community, _event = _setup_community(db)
        task = create_task(
            db, community.id, organizer,
            title="General task", description="Do something",
            task_type=TaskType.GENERAL.value, task_config={},
            required_evidence_types=["text"],
        )
        assert task.task_type == TaskType.GENERAL.value
    engine.dispose()


def test_create_video_task_with_config(tmp_path):
    """Video task stores video_url and platform in task_config."""
    sessions, engine = _make_session(tmp_path, "video.db")
    with sessions() as db:
        organizer, _member, community, _event = _setup_community(db)
        task = create_task(
            db, community.id, organizer,
            title="Watch video", description="Watch this video",
            task_type=TaskType.VIDEO.value,
            task_config={"video_url": "https://youtube.com/watch?v=abc", "platform": "YouTube"},
            required_evidence_types=["text"],
        )
        assert task.task_type == TaskType.VIDEO.value
        assert task.task_config["video_url"] == "https://youtube.com/watch?v=abc"
    engine.dispose()


def test_create_referral_task_with_config(tmp_path):
    """Referral task stores referral_target and min_referrals."""
    sessions, engine = _make_session(tmp_path, "referral.db")
    with sessions() as db:
        organizer, _member, community, _event = _setup_community(db)
        task = create_task(
            db, community.id, organizer,
            title="Invite friends", description="Invite new members",
            task_type=TaskType.REFERRAL.value,
            task_config={"referral_target": "TickVendor", "min_referrals": 3},
            required_evidence_types=["text", "url"],
        )
        assert task.task_type == TaskType.REFERRAL.value
        assert task.task_config["min_referrals"] == 3
    engine.dispose()


# ── Evidence validation ───────────────────────────────────────────────────────

def test_submit_task_requires_text_when_configured(tmp_path):
    """Submission fails when text evidence is required but not provided."""
    sessions, engine = _make_session(tmp_path, "evidence_text.db")
    with sessions() as db:
        organizer, member, community, _event = _setup_community(db)
        task = create_task(
            db, community.id, organizer,
            title="Text task", description="Needs text",
            task_type=TaskType.GENERAL.value, task_config={},
            required_evidence_types=["text"],
        )
        assignment = assign_task(db, task, member.id, organizer)
        with pytest.raises(HTTPException) as exc_info:
            submit_task(db, assignment, member, evidence_text=None, evidence_url=None)
        assert exc_info.value.status_code == 422
        assert "text" in exc_info.value.detail.lower()
    engine.dispose()


def test_submit_task_requires_url_when_configured(tmp_path):
    """Submission fails when URL evidence is required but not provided."""
    sessions, engine = _make_session(tmp_path, "evidence_url.db")
    with sessions() as db:
        organizer, member, community, _event = _setup_community(db)
        task = create_task(
            db, community.id, organizer,
            title="URL task", description="Needs URL",
            task_type=TaskType.SURVEY.value,
            task_config={"survey_url": "https://forms.example.com"},
            required_evidence_types=["url"],
        )
        assignment = assign_task(db, task, member.id, organizer)
        with pytest.raises(HTTPException) as exc_info:
            submit_task(db, assignment, member, evidence_text="I did it", evidence_url=None)
        assert exc_info.value.status_code == 422
        assert "url" in exc_info.value.detail.lower()
    engine.dispose()


def test_submit_task_succeeds_with_all_required_evidence(tmp_path):
    """Submission succeeds when all required evidence types are provided."""
    sessions, engine = _make_session(tmp_path, "evidence_all.db")
    with sessions() as db:
        organizer, member, community, _event = _setup_community(db)
        task = create_task(
            db, community.id, organizer,
            title="Full evidence task", description="Needs text and URL",
            task_type=TaskType.GENERAL.value, task_config={},
            required_evidence_types=["text", "url"],
        )
        assignment = assign_task(db, task, member.id, organizer)
        submission = submit_task(
            db, assignment, member,
            evidence_text="Here is my evidence",
            evidence_url="https://example.com/proof",
        )
        assert submission is not None
        assert submission.evidence_text == "Here is my evidence"
        assert submission.evidence_url == "https://example.com/proof"
    engine.dispose()


# ── Tenant isolation ──────────────────────────────────────────────────────────

def test_organizer_cannot_create_task_in_another_community(tmp_path):
    """An organizer from community A cannot create tasks in community B."""
    sessions, engine = _make_session(tmp_path, "tenant_isolation.db")
    with sessions() as db:
        organizer_a, _, _community_a, _ = _setup_community(db)
        # Create a second community with a different organizer.
        # Create a genuinely separate second tenant. Do not call
        # _setup_community() again because create_event_context() uses
        # fixed fixture identities such as owner@example.com.
        from src.models import Community, Organization

        organizer_b = User(
            email="tenant-b-organizer@example.com",
            password_hash="hash",
        )
        db.add(organizer_b)
        db.flush()

        organization_b = Organization(
            owner_id=organizer_b.id,
            name="Tenant B Org",
            slug="tenant-b-org",
        )
        db.add(organization_b)
        db.flush()

        community_b = Community(
            organization_id=organization_b.id,
            name="Tenant B Community",
            slug="tenant-b-community",
        )
        db.add(community_b)
        db.flush()

        db.add(
            Membership(
                community_id=community_b.id,
                user_id=organizer_b.id,
                role=MembershipRole.ORGANIZER,
                status=MembershipStatus.ACTIVE,
            )
        )
        db.commit()
        # organizer_a tries to create a task in community_b — should fail.
        with pytest.raises(HTTPException) as exc_info:
            create_task(
                db, community_b.id, organizer_a,
                title="Cross-tenant task", description="Should not be allowed",
                task_type=TaskType.GENERAL.value, task_config={},
                required_evidence_types=["text"],
            )
        assert exc_info.value.status_code in (403, 404)
    engine.dispose()


def test_member_cannot_access_task_verification_queue(tmp_path):
    """A regular member gets 403 when accessing the task verification queue."""
    from fastapi.testclient import TestClient

    from src.database import get_db
    from src.main import create_app
    from src.security import create_access_token

    engine = create_engine(
        f"sqlite:///{tmp_path / 'queue_auth.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()

    def override_get_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    with sessions() as db:
        organizer, community, _event = create_event_context(db)
        member = User(email="queue-member@example.com", password_hash="hash")
        db.add(member)
        db.flush()
        db.add_all([
            Membership(community_id=community.id, user_id=organizer.id, role=MembershipRole.ORGANIZER, status=MembershipStatus.ACTIVE),
            Membership(community_id=community.id, user_id=member.id, role=MembershipRole.MEMBER, status=MembershipStatus.ACTIVE),
        ])
        db.commit()
        community_id = str(community.id)
        member_id = str(member.id)

    member_token = create_access_token(member_id, "participant")
    response = client.get(
        f"/api/v1/communities/{community_id}/task-verification-queue",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert response.status_code == 403, f"Expected 403, got {response.status_code}"
    engine.dispose()


# ── Category API authorization ────────────────────────────────────────────────

def test_ordinary_admin_cannot_mutate_categories(tmp_path):
    """A community admin (not super_admin) gets 403 on POST /admin/categories."""
    from fastapi.testclient import TestClient

    from src.database import get_db
    from src.main import create_app
    from src.models import PlatformRole
    from src.security import create_access_token

    engine = create_engine(
        f"sqlite:///{tmp_path / 'cat_auth.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()

    def override_get_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    with sessions() as db:
        community_admin = User(email="cadmin@example.com", password_hash="hash", role=PlatformRole.PARTICIPANT)
        db.add(community_admin)
        db.commit()
        admin_id = str(community_admin.id)

    # Community admin (platform role = participant) tries to create a category.
    token = create_access_token(admin_id, "participant")
    response = client.post(
        "/api/v1/admin/categories",
        json={"slug": "test-cat", "name": "Test Category"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403, f"Expected 403, got {response.status_code}"
    engine.dispose()


def test_public_events_categories_endpoint_returns_active(tmp_path):
    """GET /events/categories returns only active categories without auth."""
    from fastapi.testclient import TestClient

    from src.database import get_db
    from src.main import create_app
    from src.models import EventCategory

    engine = create_engine(
        f"sqlite:///{tmp_path / 'events_cats.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()

    def override_get_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    with sessions() as db:
        db.add(EventCategory(slug="tech", name="Technology", is_active=True))
        db.add(EventCategory(slug="inactive", name="Inactive", is_active=False))
        db.commit()

    # No auth required.
    response = client.get("/api/v1/events/categories")
    assert response.status_code == 200, response.text
    slugs = [c["slug"] for c in response.json()]
    assert "tech" in slugs
    assert "inactive" not in slugs
    engine.dispose()
