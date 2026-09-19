"""Platform RBAC and community tenant-boundary helpers.

Two authority shapes exist below the platform role, and keeping them apart is the point:

* **Community governance** is community-wide. ``require_community_role`` expresses it, and it is
  the right gate for membership administration, configuration, analytics and audit.
* **Operational delivery** is resource-scoped. ``require_event_staff_authority`` and
  ``require_task_management_authority`` express it: an Organizer runs the events and tasks they
  own, and delivers them through narrow, per-event EventStaff delegation, not by holding a
  community-wide Organizer badge.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.models import (
    Community,
    EventStaff,
    EventStaffRole,
    Membership,
    MembershipRole,
    MembershipStatus,
    PlatformRole,
    User,
)

ROLE_RANK = {
    MembershipRole.MEMBER: 1,
    MembershipRole.ORGANIZER: 2,
    MembershipRole.ADMIN: 3,
}

# Event-staff role groups, passed to ``require_event_staff_authority`` as ``staff_roles``.
#
# Each is a closed allow-list rather than a rank, so a role added to ``EventStaffRole`` later
# inherits none of them by default: it has to be named here deliberately before it can do the
# work. ``staff_roles=None`` means "any active role on this event" and is reserved for questions
# that are not authority gates at all.
#
# Running an event: its ticket inventory, its benefit configuration, its operational reporting.
# This is configuration with money attached, so it stays with the one role named for running the
# event, and the three single-job roles below do not reach it.
EVENT_MANAGEMENT_STAFF_ROLES = (EventStaffRole.MANAGER,)

# Admitting attendees at the venue: scanning a ticket, marking QR attendance, redeeming a benefit.
# MANAGER is included because it runs the whole event, and ATTENDANCE_VERIFIER because it may
# already overwrite the attendance record outright — refusing it the door scan while it holds the
# stronger authority over the same record would protect nothing.
EVENT_ADMISSION_STAFF_ROLES = (
    EventStaffRole.MANAGER,
    EventStaffRole.CHECK_IN,
    EventStaffRole.TICKET_VALIDATOR,
    EventStaffRole.ATTENDANCE_VERIFIER,
)

# Adjudicating attendance records: resolving the review queue and reading the roster. Narrower
# than admission on purpose — a door scanner admits people but does not overturn a flagged record.
EVENT_ATTENDANCE_STAFF_ROLES = (EventStaffRole.MANAGER, EventStaffRole.ATTENDANCE_VERIFIER)


def _acting_admin_membership(community_id: UUID, user: User) -> Membership:
    """Stand-in membership for Super Admin, who holds platform-wide authority without a row."""
    return Membership(
        community_id=community_id,
        user_id=user.id,
        role=MembershipRole.ADMIN,
        status=MembershipStatus.ACTIVE,
    )


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
        return _acting_admin_membership(community_id, current_user)
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


def _active_event_staff(db: Session, event, user: User, staff_roles) -> bool:
    criteria = [
        EventStaff.event_id == event.id,
        EventStaff.user_id == user.id,
        EventStaff.is_active.is_(True),
    ]
    if staff_roles:
        criteria.append(EventStaff.role.in_(tuple(staff_roles)))
    return db.scalar(select(EventStaff.id).where(*criteria)) is not None


def require_event_ownership_authority(db: Session, event, user: User) -> Membership:
    """Authorize an action only the event's owner, a community Admin, or Super Admin may take.

    Used for authority that must not be delegated onward — appointing or revoking EventStaff.
    """
    if user.role == PlatformRole.SUPER_ADMIN:
        return _acting_admin_membership(event.community_id, user)
    # Enforces the tenant boundary, community suspension and an active (non-left) membership.
    membership = require_community_role(db, event.community_id, user, MembershipRole.MEMBER)
    if membership.role == MembershipRole.ADMIN or event.organizer_id == user.id:
        return membership
    raise HTTPException(status_code=403, detail="Event ownership required")


def require_event_staff_authority(db: Session, event, user: User, *, staff_roles=None) -> Membership:
    """Authorize one operational action against a single event.

    Event operations are owner-scoped, never community-wide: an active Organizer membership in
    the event's community is *not* by itself authority over somebody else's event. A caller
    passes when they are the platform Super Admin, the event's owner, an active EventStaff member
    of that event (optionally narrowed to ``staff_roles``), or an Admin of the event's community.

    ``staff_roles`` should be one of the ``EVENT_*_STAFF_ROLES`` groups above rather than an
    ad-hoc tuple, so that the authority each operational job carries is declared in one place.

    Everyone else — including a fellow Organizer with no staff assignment — receives 403, which
    is why delegating one job on one event is preferable to widening somebody's community role.
    """
    if user.role == PlatformRole.SUPER_ADMIN:
        return _acting_admin_membership(event.community_id, user)
    # Enforces the tenant boundary, community suspension and an active (non-left) membership, so
    # an Organizer of another community can never reach this event even as staff.
    membership = require_community_role(db, event.community_id, user, MembershipRole.MEMBER)
    if membership.role == MembershipRole.ADMIN or event.organizer_id == user.id:
        return membership
    if _active_event_staff(db, event, user, staff_roles):
        return membership
    raise HTTPException(status_code=403, detail="Event staff authority required")


def require_task_management_authority(db: Session, task, user: User, *, action: str = "manage") -> Membership:
    """Authorize administration of one task.

    Organizers operate the tasks they created; community Admins oversee every task in their
    community; Super Admins retain platform-wide authority. An Organizer who did not create the
    task cannot edit, assign, verify or reconfigure it — otherwise any Organizer could silently
    rewrite a colleague's reward, evidence requirements or assignee list.

    Participant access to an assignment is governed separately and is not narrowed here.
    """
    if user.role == PlatformRole.SUPER_ADMIN:
        return _acting_admin_membership(task.community_id, user)
    membership = require_community_role(db, task.community_id, user, MembershipRole.ORGANIZER)
    if membership.role == MembershipRole.ADMIN or task.created_by_id == user.id:
        return membership
    raise HTTPException(status_code=403, detail=f"Task ownership required to {action} this task")


def require_resource_owner_or_super_admin(owner_id: UUID, current_user: User) -> None:
    if current_user.id != owner_id and current_user.role != PlatformRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Resource ownership required")
