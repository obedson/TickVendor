"""Idempotent development/demo bootstrap seed for a complete local journey."""
import os
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{ROOT / '.tmp-demo.db'}")
os.environ.setdefault("ENVIRONMENT", "development")

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.database import Base
from src.models import (
    Activity,
    ActivityStatus,
    Community,
    EngagementDimension,
    Event,
    EventStatus,
    LocationType,
    Membership,
    MembershipRole,
    MembershipStatus,
    Organization,
    PlatformRole,
    Profile,
    Task,
    TaskAssignment,
    TicketType,
    TicketVisibility,
    User,
)
from src.security import hash_password
from src.seed import seed_business_configuration, seed_community_recognition


def main() -> None:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_business_configuration(db)
        password = hash_password("demo-password-123")
        users = {}
        for email, username, role in [
            ("demo-participant@example.com", "demo-participant", PlatformRole.PARTICIPANT),
            ("demo-organizer@example.com", "demo-organizer", PlatformRole.PARTICIPANT),
            ("demo-admin@example.com", "demo-admin", PlatformRole.SUPER_ADMIN),
        ]:
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(email=email, password_hash=password, role=role, email_verified_at=datetime.now(UTC), profile=Profile(username=username, display_name=username.replace("demo-", "Demo ").title()))
                db.add(user); db.flush()
            users[username] = user
        org = db.scalar(select(Organization).where(Organization.slug == "demo-organization"))
        if org is None:
            org = Organization(owner_id=users["demo-organizer"].id, name="Demo Organization", slug="demo-organization"); db.add(org); db.flush()
        community = db.scalar(select(Community).where(Community.slug == "demo-community"))
        if community is None:
            community = Community(organization_id=org.id, name="Demo Community", slug="demo-community"); db.add(community); db.flush()
        for user, role in [(users["demo-participant"], MembershipRole.MEMBER), (users["demo-organizer"], MembershipRole.ADMIN), (users["demo-admin"], MembershipRole.ADMIN)]:
            if db.scalar(select(Membership).where(Membership.community_id == community.id, Membership.user_id == user.id)) is None:
                db.add(Membership(community_id=community.id, user_id=user.id, role=role, status=MembershipStatus.ACTIVE))
        event = db.scalar(select(Event).where(Event.slug == "demo-community-event"))
        if event is None:
            event = Event(community_id=community.id, organizer_id=users["demo-organizer"].id, title="Demo Community Event", slug="demo-community-event", description="A complete local TickVendor journey.", category="community", starts_at=datetime.now(UTC)+timedelta(days=2), ends_at=datetime.now(UTC)+timedelta(days=2, hours=2), location_type=LocationType.ONLINE, status=EventStatus.PUBLISHED, published_at=datetime.now(UTC)); db.add(event); db.flush()
            db.add(TicketType(event_id=event.id, name="Demo free ticket", description="Demo admission", price=Decimal(0), quantity=100, visibility=TicketVisibility.PUBLIC, max_per_user=2))
        task = db.scalar(select(Task).where(Task.community_id == community.id, Task.title == "Demo welcome task"))
        if task is None:
            task = Task(community_id=community.id, event_id=event.id, created_by_id=users["demo-organizer"].id, title="Demo welcome task", description="Complete the demo welcome task.", due_at=datetime.now(UTC)+timedelta(days=3), impact_point_reward=5, verification_required=True); db.add(task); db.flush(); db.add(TaskAssignment(task_id=task.id, assignee_id=users["demo-participant"].id, assigned_by_id=users["demo-organizer"].id))
        if db.scalar(select(Activity.id).where(Activity.community_id == community.id, Activity.activity_type == "demo-volunteer")) is None:
            db.add(Activity(community_id=community.id, user_id=users["demo-participant"].id, activity_type="demo-volunteer", description="A seeded verified service activity.", dimension=EngagementDimension.SERVICE, status=ActivityStatus.VERIFIED, occurred_at=datetime.now(UTC)))
        db.commit()
        seed_community_recognition(db, community.id)
    engine.dispose()


if __name__ == "__main__":
    main()
