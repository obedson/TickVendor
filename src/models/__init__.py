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
    CommunityLifecycleStatus,
    Membership,
    MembershipAccess,
    MembershipRole,
    MembershipStatus,
)
from src.models.configuration import (
    ContributionBand,
    EventCategory,
    NotificationRule,
    PointCeiling,
    PointRule,
)
from src.models.contribution import (
    Activity,
    ActivityStatus,
    Contribution,
    ContributionType,
    EngagementDimension,
)
from src.models.entitlement import (
    Entitlement,
    EntitlementRedemption,
    RedemptionMode,
    RedemptionStatus,
    TicketEntitlement,
    TicketEntitlementStatus,
)
from src.models.event import (
    Event,
    EventStaff,
    EventStaffRole,
    EventStatus,
    LocationType,
    Venue,
)
from src.models.external_identity import ExternalIdentity, GoogleAuthFlow
from src.models.impact import ImpactTransaction, ImpactTransactionStatus
from src.models.milestone import Milestone, MilestoneAward, MilestoneRequirement
from src.models.notification import AuditLog, Leaderboard, Notification
from src.models.opportunity import (
    ActivityOpportunity,
    OpportunityRegistration,
    OpportunityRegistrationStatus,
    OpportunityStatus,
)
from src.models.organization import Organization
from src.models.payment import Payment, PaymentStatus
from src.models.personal_archive import PersonalArchive
from src.models.preference import NotificationPreference
from src.models.promotion import Promotion
from src.models.rank import Rank, RankProgression, RankRequirement
from src.models.scheduled_notification import ScheduledNotification, ScheduledNotificationStatus
from src.models.task import (
    Task,
    TaskAssignment,
    TaskAssignmentStatus,
    TaskPriority,
    TaskSubmission,
    TaskType,
)
from src.models.task_attachment import TaskAttachment
from src.models.ticket import (
    Order,
    OrderStatus,
    Ticket,
    TicketAssignmentState,
    TicketStatus,
    TicketTransfer,
    TicketType,
    TicketVisibility,
    TransferStatus,
)
from src.models.user import PlatformRole, Profile, ProfileVisibility, User

__all__ = [
    "AchievementAward",
    "AchievementRule",
    "Activity",
    "ActivityOpportunity",
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
    "CommunityLifecycleStatus",
    "Contribution",
    "ContributionBand",
    "ContributionType",
    "EngagementDimension",
    "Entitlement",
    "EntitlementRedemption",
    "Event",
    "EventCategory",
    "EventStaff",
    "EventStaffRole",
    "EventStatus",
    "ExternalIdentity",
    "GoogleAuthFlow",
    "ImpactTransaction",
    "ImpactTransactionStatus",
    "Leaderboard",
    "LocationType",
    "Membership",
    "MembershipAccess",
    "MembershipRole",
    "MembershipStatus",
    "Milestone",
    "MilestoneAward",
    "MilestoneRequirement",
    "Notification",
    "NotificationPreference",
    "NotificationRule",
    "OpportunityRegistration",
    "OpportunityRegistrationStatus",
    "OpportunityStatus",
    "Order",
    "OrderStatus",
    "Organization",
    "Payment",
    "PaymentStatus",
    "PeerConfirmation",
    "PeerConfirmationDecision",
    "PersonalArchive",
    "PlatformRole",
    "PointCeiling",
    "PointRule",
    "Profile",
    "ProfileVisibility",
    "Promotion",
    "Rank",
    "RankProgression",
    "RankRequirement",
    "RedemptionMode",
    "RedemptionStatus",
    "ScheduledNotification",
    "ScheduledNotificationStatus",
    "Task",
    "TaskAssignment",
    "TaskAssignmentStatus",
    "TaskAttachment",
    "TaskPriority",
    "TaskSubmission",
    "TaskType",
    "Ticket",
    "TicketAssignmentState",
    "TicketEntitlement",
    "TicketEntitlementStatus",
    "TicketStatus",
    "TicketTransfer",
    "TicketType",
    "TicketVisibility",
    "TransferStatus",
    "User",
    "Venue",
    "VerificationMethod",
]
