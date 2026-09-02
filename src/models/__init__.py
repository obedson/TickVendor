"""Model registry.

Import every SQLAlchemy model module here so metadata and Alembic discover it.
"""

from src.models.achievement import AchievementAward, AchievementRule
from src.models.attendance import (
    Attendance,
    AttendanceReviewStatus,
    AttendanceStatus,
    AttendanceVerification,
    PeerConfirmation,
    PeerConfirmationDecision,
    VerificationMethod,
)
from src.models.auth import AuthSession, AuthToken, AuthTokenPurpose
from src.models.badge import Badge, BadgeAward
from src.models.community import (
    Community,
    Membership,
    MembershipRole,
    MembershipStatus,
)
from src.models.configuration import ContributionBand, EventCategory, PointRule
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
from src.models.milestone import Milestone, MilestoneAward, MilestoneRequirement
from src.models.notification import AuditLog, Leaderboard, Notification
from src.models.organization import Organization
from src.models.payment import Payment, PaymentStatus
from src.models.preference import NotificationPreference
from src.models.rank import Rank, RankProgression, RankRequirement
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
    "AchievementAward",
    "AchievementRule",
    "Activity",
    "ActivityStatus",
    "Attendance",
    "AttendanceReviewStatus",
    "AttendanceStatus",
    "AttendanceVerification",
    "AuditLog",
    "AuthSession",
    "AuthToken",
    "AuthTokenPurpose",
    "Badge",
    "BadgeAward",
    "Community",
    "Contribution",
    "ContributionBand",
    "ContributionType",
    "EngagementDimension",
    "Event",
    "EventCategory",
    "EventStaff",
    "EventStaffRole",
    "EventStatus",
    "ImpactTransaction",
    "ImpactTransactionStatus",
    "Leaderboard",
    "LocationType",
    "Membership",
    "MembershipRole",
    "MembershipStatus",
    "Milestone",
    "MilestoneAward",
    "MilestoneRequirement",
    "Notification",
    "NotificationPreference",
    "Order",
    "OrderStatus",
    "Organization",
    "Payment",
    "PaymentStatus",
    "PeerConfirmation",
    "PeerConfirmationDecision",
    "PlatformRole",
    "PointRule",
    "Profile",
    "ProfileVisibility",
    "Rank",
    "RankProgression",
    "RankRequirement",
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