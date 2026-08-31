"""Model registry.

Import every SQLAlchemy model module here so metadata and Alembic discover it.
"""

from src.models.community import (
    Community,
    Membership,
    MembershipRole,
    MembershipStatus,
)
from src.models.organization import Organization
from src.models.user import PlatformRole, Profile, ProfileVisibility, User

__all__ = [
    "Community",
    "Membership",
    "MembershipRole",
    "MembershipStatus",
    "Organization",
    "PlatformRole",
    "Profile",
    "ProfileVisibility",
    "User",
]