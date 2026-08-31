"""Model registry.

Import every SQLAlchemy model module here so metadata and Alembic discover it.
"""

from src.models.user import PlatformRole, Profile, ProfileVisibility, User

__all__ = ["PlatformRole", "Profile", "ProfileVisibility", "User"]