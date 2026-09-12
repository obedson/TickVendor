"""Platform RBAC and community tenant-boundary helpers."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.models import Community, Membership, MembershipRole, MembershipStatus, PlatformRole, User

ROLE_RANK = {
    MembershipRole.MEMBER: 1,
    MembershipRole.ORGANIZER: 2,
    MembershipRole.ADMIN: 3,
}


def require_platform_roles(*allowed: PlatformRole) -> Callable[[User], User]:
    def dependency(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.role not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient platform role")
        return current_user

    return dependency


def require_community_role(
    db: Session,
    community_id: UUID,
    current_user: User,
    minimum_role: MembershipRole = MembershipRole.MEMBER,
) -> Membership:
    community = db.get(Community, community_id)
    if community is None or community.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Community not found")
    if current_user.role == PlatformRole.SUPER_ADMIN:
        return Membership(
            community_id=community_id,
            user_id=current_user.id,
            role=MembershipRole.ADMIN,
            status=MembershipStatus.ACTIVE,
        )
    if not community.is_active:
        raise HTTPException(status_code=403, detail="Community is suspended")
    membership = db.scalar(
        select(Membership).where(
            Membership.community_id == community_id,
            Membership.user_id == current_user.id,
            Membership.status == MembershipStatus.ACTIVE,
        )
    )
    if membership is None or ROLE_RANK[membership.role] < ROLE_RANK[minimum_role]:
        raise HTTPException(status_code=403, detail="Insufficient community role")
    return membership


def require_resource_owner_or_super_admin(owner_id: UUID, current_user: User) -> None:
    if current_user.id != owner_id and current_user.role != PlatformRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Resource ownership required")
