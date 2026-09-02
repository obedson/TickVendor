"""Seed an isolated local database for real participant browser tests."""
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ["DATABASE_URL"] = f"sqlite:///{ROOT / '.tmp-e2e.db'}"
os.environ["ENVIRONMENT"] = "test"
os.environ["PAYMENT_PROVIDER"] = "test"

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401,E402
from src.database import Base  # noqa: E402
from src.models import (  # noqa: E402
    Attendance, AttendanceStatus, Community, Event, EventCategory, EventStatus, LocationType, Membership, MembershipRole,
    MembershipStatus, Organization, PlatformRole, PointRule, Profile, Task,
    TaskAssignment, Ticket, TicketStatus, TicketType, TicketVisibility, User,
)
from src.security import hash_password  # noqa: E402


def main() -> None:
    database = ROOT / ".tmp-e2e.db"
    database.unlink(missing_ok=True)
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    with Session(engine) as db:
        participant = User(
            email="e2e-participant@example.com", password_hash=hash_password("e2e-password-123"),
            role=PlatformRole.PARTICIPANT, email_verified_at=now,
            profile=Profile(username="e2e-participant", display_name="E2E Participant"),
        )
        organizer = User(
            email="e2e-organizer@example.com", password_hash=hash_password("e2e-password-123"),
            role=PlatformRole.ORGANIZER, email_verified_at=now,
            profile=Profile(username="e2e-organizer", display_name="E2E Organizer"),
        )
        peer = User(
            email="e2e-peer@example.com", password_hash=hash_password("e2e-password-123"),
            role=PlatformRole.PARTICIPANT, email_verified_at=now,
            profile=Profile(username="e2e-peer", display_name="E2E Peer"),
        )
        db.add_all([participant, organizer, peer]); db.flush()
        db.add(EventCategory(slug="community", name="Community"))
        organization = Organization(owner_id=organizer.id, name="E2E Organization", slug="e2e-organization")
        db.add(organization); db.flush()
        community = Community(organization_id=organization.id, name="E2E Community", slug="e2e-community")
        db.add(community); db.flush()
        db.add_all([
            Membership(community_id=community.id, user_id=participant.id, role=MembershipRole.MEMBER, status=MembershipStatus.ACTIVE),
            Membership(community_id=community.id, user_id=organizer.id, role=MembershipRole.ORGANIZER, status=MembershipStatus.ACTIVE),
            Membership(community_id=community.id, user_id=peer.id, role=MembershipRole.MEMBER, status=MembershipStatus.ACTIVE),
        ])
        event = Event(
            community_id=community.id, organizer_id=organizer.id, title="E2E Community Meetup",
            slug="e2e-community-meetup", description="A deterministic participant event.", category="community",
            starts_at=now + timedelta(hours=1), ends_at=now + timedelta(hours=3),
            location_type=LocationType.ONLINE, status=EventStatus.PUBLISHED, published_at=now,
            peer_confirmation_enabled=True, confirmations_required=1, max_peer_confirmations=3,
            peer_selection_limit=5, required_verification_methods=["peer"],
        )
        db.add(event); db.flush()
        ticket_type = TicketType(event_id=event.id, name="Free admission", description="No-cost entry", price=0,
                                 quantity=10, visibility=TicketVisibility.PUBLIC, max_per_user=1)
        paid_type = TicketType(event_id=event.id, name="Supporter admission", description="Paid entry",
                               price=100, quantity=10, visibility=TicketVisibility.PUBLIC, max_per_user=1)
        db.add_all([ticket_type, paid_type]); db.flush()
        db.add(Ticket(public_id="E2EPEER0000000000000001", qr_token="e2e-peer-qr-token-000000000000000000000000000000000000000000",
                      event_id=event.id, ticket_type_id=ticket_type.id, attendee_id=peer.id, status=TicketStatus.ACTIVE))
        db.add(Attendance(event_id=event.id, user_id=peer.id, status=AttendanceStatus.CHECKED_IN,
                          checked_in_at=now))
        task = Task(community_id=community.id, event_id=event.id, created_by_id=organizer.id,
                    title="Welcome task", description="Complete the welcome check-in task.",
                    due_at=now + timedelta(days=1), impact_point_reward=5, verification_required=True)
        db.add(task); db.flush()
        db.add(TaskAssignment(task_id=task.id, assignee_id=participant.id, assigned_by_id=organizer.id))
        db.add(PointRule(community_id=community.id, source_type="task_completion", points=5, is_active=True))
        db.commit()
    engine.dispose()


if __name__ == "__main__":
    main()
