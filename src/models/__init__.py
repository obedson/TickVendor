"""Model registry.

Import every SQLAlchemy model module here so metadata and Alembic discover it.
"""

from src.models.attendance import (
    Attendance,
    AttendanceStatus,
    AttendanceVerification,
    PeerConfirmation,
    PeerConfirmationDecision,
    VerificationMethod,
)
from src.models.community import (
    Community,
    Membership,
    MembershipRole,
    MembershipStatus,
)
from src.models.contribution import (
    Activity,
    ActivityStatus,
    Contribution,
    ContributionType,
    EngagementDimension,
)
from src.models.event import (
    Event,
    EventStaff,
    EventStaffRole,
    EventStatus,
    LocationType,
    Venue,
)
from src.models.impact import ImpactTransaction, ImpactTransactionStatus
from src.models.organization import Organization
from src.models.payment import Payment, PaymentStatus
from src.models.task import (
    Task,
    TaskAssignment,
    TaskAssignmentStatus,
    TaskPriority,
    TaskSubmission,
)
from src.models.ticket import (
    Order,
    OrderStatus,
    Ticket,
    TicketStatus,
    TicketType,
    TicketVisibility,
)
from src.models.user import PlatformRole, Profile, ProfileVisibility, User

__all__ = [
    "Activity",
    "ActivityStatus",
    "Attendance",
    "AttendanceStatus",
    "AttendanceVerification",
    "Community",
    "Contribution",
    "ContributionType",
    "EngagementDimension",
    "Event",
    "EventStaff",
    "EventStaffRole",
    "EventStatus",
    "ImpactTransaction",
    "ImpactTransactionStatus",
    "LocationType",
    "Membership",
    "MembershipRole",
    "MembershipStatus",
    "Order",
    "OrderStatus",
    "Organization",
    "Payment",
    "PaymentStatus",
    "PeerConfirmation",
    "PeerConfirmationDecision",
    "PlatformRole",
    "Profile",
    "ProfileVisibility",
    "Task",
    "TaskAssignment",
    "TaskAssignmentStatus",
    "TaskPriority",
    "TaskSubmission",
    "Ticket",
    "TicketStatus",
    "TicketType",
    "TicketVisibility",
    "User",
    "Venue",
    "VerificationMethod",
]