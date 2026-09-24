"""Explicit, audited governance transitions. No financial/history deletions."""
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.authorization import require_community_role
from src.models import (
    ActivityOpportunity,
    AuthSession,
    Community,
    CommunityLifecycleStatus,
    Event,
    Membership,
    MembershipAccess,
    MembershipRole,
    MembershipStatus,
    Organization,
    PlatformRole,
    Task,
    User,
)
from src.services.notification import audit, notify


def platform_only(user: User):
    if user.role != PlatformRole.SUPER_ADMIN:
        raise HTTPException(403, "Super Admin required")


def community_for_update(db: Session, community_id: UUID, *, active=True):
    community = db.scalar(select(Community).where(Community.id == community_id).with_for_update())
    if community is None or community.deleted_at is not None or (
        active and (
            not community.is_active
            or community.lifecycle_status != CommunityLifecycleStatus.ACTIVE
        )
    ):
        raise HTTPException(404, "Community not found")
    return community


def member_for(db, community_id, user_id):
    return db.scalar(select(Membership).where(Membership.community_id == community_id, Membership.user_id == user_id))


def active_admin_count(db: Session, community_id: UUID) -> int:
    return len(list(db.scalars(select(Membership.id).where(
        Membership.community_id == community_id,
        Membership.role == MembershipRole.ADMIN,
        Membership.status == MembershipStatus.ACTIVE,
    ))))


def active_verified_admin_count(db: Session, community_id: UUID) -> int:
    return len(list(db.scalars(select(Membership.id).join(User, User.id == Membership.user_id).where(
        Membership.community_id == community_id,
        Membership.role == MembershipRole.ADMIN,
        Membership.status == MembershipStatus.ACTIVE,
        User.is_active.is_(True),
        User.email_verified_at.is_not(None),
    ))))


def require_verified_admin_candidate(target: User | None) -> User:
    if target is None or not target.is_active:
        raise HTTPException(404, "Active user not found")
    if target.email_verified_at is None:
        raise HTTPException(422, "Community administrators must have a verified email")
    if target.role == PlatformRole.SUPER_ADMIN:
        raise HTTPException(403, "Super Admin authority must remain separate from community membership")
    return target


def record_membership(db, item, actor, action, previous, reason):
    db.flush()
    audit(db, actor_id=actor.id, community_id=item.community_id, action=f"membership.{action}",
          target_type="membership", target_id=item.id, metadata={"reason": reason, "previous": previous,
          "result": {"role": item.role.value, "status": item.status.value}}, commit=False)
    if actor.id != item.user_id:
        community = db.get(Community, item.community_id)
        notify(db, item.user_id, f"membership_{action}", "Community membership updated",
               f"{community.name}: {action.replace('_', ' ')}. {reason}",
               {"community_id": str(item.community_id)}, community_id=item.community_id, commit=False)


def state(item):
    return {"role": item.role.value, "status": item.status.value} if item else None


def participant_transition(db: Session, community_id: UUID, user: User, action: str):
    community = community_for_update(db, community_id, active=action not in {"leave", "withdraw", "decline"})
    item = member_for(db, community_id, user.id)
    before = state(item)
    if action == "join":
        if not community.is_public and item is None:
            raise HTTPException(404, "Community not found")
        if item and item.status in {MembershipStatus.ACTIVE, MembershipStatus.PENDING}:
            return item
        if community.membership_access == MembershipAccess.INVITE_ONLY:
            raise HTTPException(403, "An invitation is required")
        if item and item.status not in {MembershipStatus.LEFT, MembershipStatus.DECLINED}:
            raise HTTPException(409, "Membership requires administrator action or invitation response")
        if item is None:
            item = Membership(community_id=community_id, user_id=user.id)
            db.add(item)
        item.role = MembershipRole.MEMBER
        item.status = MembershipStatus.ACTIVE if community.membership_access == MembershipAccess.OPEN else MembershipStatus.PENDING
        action = "joined" if item.status == MembershipStatus.ACTIVE else "requested"
    else:
        if item is None:
            raise HTTPException(404, "Membership not found")
        transitions = {
            "accept": (MembershipStatus.INVITED, MembershipStatus.ACTIVE),
            "decline": (MembershipStatus.INVITED, MembershipStatus.DECLINED),
            "withdraw": (MembershipStatus.PENDING, MembershipStatus.LEFT),
            "leave": (MembershipStatus.ACTIVE, MembershipStatus.LEFT),
        }
        if action not in transitions:
            raise HTTPException(422, "Unknown membership action")
        source, target = transitions[action]
        if item.status == target:
            return item
        if item.status != source:
            raise HTTPException(409, "Invalid membership transition")
        if action == "leave" and item.role == MembershipRole.ADMIN:
            raise HTTPException(409, "Ask a Super Admin to change your administrator role before leaving")
        item.status = target
    if item.status == MembershipStatus.ACTIVE:
        item.joined_at = datetime.now(UTC)
    record_membership(db, item, user, action, before, "Participant initiated")
    if item.status == MembershipStatus.PENDING:
        for admin_id in db.scalars(select(Membership.user_id).where(Membership.community_id == community_id,
                Membership.role == MembershipRole.ADMIN, Membership.status == MembershipStatus.ACTIVE)):
            notify(db, admin_id, "membership_requested", "Join request", f"A participant requested to join {community.name}.",
                   {"community_id": str(community_id)}, community_id=community_id, commit=False)
    db.commit()
    return item


def invite(db, community_id, actor, target_id, role):
    community_for_update(db, community_id)
    require_community_role(db, community_id, actor, MembershipRole.ADMIN)
    target = db.get(User, target_id)
    if target is None or not target.is_active:
        raise HTTPException(404, "User not found")
    item = member_for(db, community_id, target_id)
    if actor.id == target_id or (actor.role != PlatformRole.SUPER_ADMIN and
            (role == MembershipRole.ADMIN or item and item.role == MembershipRole.ADMIN)):
        raise HTTPException(403, "Cannot assign or change administrator authority")
    if item and item.status == MembershipStatus.INVITED and item.role == role:
        return item
    if item and item.status not in {MembershipStatus.LEFT, MembershipStatus.DECLINED}:
        raise HTTPException(409, "Membership already exists")
    before = state(item)
    if item is None:
        item = Membership(community_id=community_id, user_id=target_id)
        db.add(item)
    item.role, item.status = role, MembershipStatus.INVITED
    record_membership(db, item, actor, "invited", before, "Community invitation")
    db.commit()
    return item


def manage_membership(db, community_id, member_id, actor, action, reason, role=None):
    if len(reason.strip()) < 3:
        raise HTTPException(422, "A meaningful reason is required")
    community_for_update(db, community_id, active=actor.role != PlatformRole.SUPER_ADMIN)
    if actor.role != PlatformRole.SUPER_ADMIN:
        require_community_role(db, community_id, actor, MembershipRole.ADMIN)
    item = db.scalar(select(Membership).where(
        Membership.id == member_id,
        Membership.community_id == community_id,
    ).with_for_update())
    if item is None:
        raise HTTPException(404, "Membership not found")
    if item.user_id == actor.id:
        raise HTTPException(403, "Cannot change your own membership authority")
    if actor.role != PlatformRole.SUPER_ADMIN and (item.role == MembershipRole.ADMIN or role == MembershipRole.ADMIN):
        raise HTTPException(403, "Only Super Admin can manage community administrators")
    removes_active_admin = (
        item.role == MembershipRole.ADMIN
        and item.status == MembershipStatus.ACTIVE
        and (action == "deactivated" or (action == "role_changed" and role != MembershipRole.ADMIN))
    )
    if removes_active_admin:
        target = db.get(User, item.user_id)
        removes_final_admin = active_admin_count(db, community_id) <= 1
        removes_final_verified_admin = (
            target is not None
            and target.is_active
            and target.email_verified_at is not None
            and active_verified_admin_count(db, community_id) <= 1
        )
        if removes_final_admin or removes_final_verified_admin:
            raise HTTPException(409, "Assign another active, verified Community Admin before removing this administrator")
    if (action == "role_changed" and role == MembershipRole.ADMIN) or (
        action == "activated" and item.role == MembershipRole.ADMIN
    ):
        require_verified_admin_candidate(db.get(User, item.user_id))
    before = state(item)
    if action == "role_changed":
        if item.status not in {MembershipStatus.ACTIVE, MembershipStatus.SUSPENDED}:
            raise HTTPException(409, "Only established memberships can change role")
        if item.role == role:
            return item
        item.role = role
    else:
        transitions = {
            "approved": ({MembershipStatus.PENDING}, MembershipStatus.ACTIVE),
            "rejected": ({MembershipStatus.PENDING}, MembershipStatus.DECLINED),
            "deactivated": ({MembershipStatus.ACTIVE}, MembershipStatus.SUSPENDED),
            "activated": ({MembershipStatus.SUSPENDED}, MembershipStatus.ACTIVE),
        }
        if action not in transitions:
            raise HTTPException(422, "Unknown membership action")
        sources, target = transitions[action]
        if item.status == target:
            return item
        if item.status not in sources:
            raise HTTPException(409, "Invalid membership transition")
        item.status = target
        if action == "approved":
            item.role = MembershipRole.MEMBER
            item.joined_at = datetime.now(UTC)
    record_membership(db, item, actor, action, before, reason)
    db.commit()
    return item


def assign_admin(db, community_id, target_id, actor, reason):
    platform_only(actor)
    if len(reason.strip()) < 3:
        raise HTTPException(422, "A meaningful reason is required")
    community = community_for_update(db, community_id, active=False)
    if community.lifecycle_status in {
        CommunityLifecycleStatus.DRAFT,
        CommunityLifecycleStatus.PENDING_REVIEW,
        CommunityLifecycleStatus.REJECTED,
    }:
        raise HTTPException(409, "Review the community application before assigning administrators")
    target = require_verified_admin_candidate(db.get(User, target_id))
    if target.id == actor.id:
        raise HTTPException(403, "Super Admin does not need to assign themselves community authority")
    item = member_for(db, community_id, target_id)
    before = state(item)
    if item and item.role == MembershipRole.ADMIN and item.status == MembershipStatus.ACTIVE:
        return item
    if item is None:
        item = Membership(community_id=community_id, user_id=target_id)
        db.add(item)
    item.role, item.status, item.joined_at = MembershipRole.ADMIN, MembershipStatus.ACTIVE, datetime.now(UTC)
    record_membership(db, item, actor, "admin_assigned", before, reason)
    db.commit()
    return item


def review_community_application(
    db: Session,
    community_id: UUID,
    actor: User,
    *,
    approve: bool,
    reason: str,
    initial_admin_user_id: UUID | None = None,
) -> Community:
    platform_only(actor)
    if len(reason.strip()) < 3:
        raise HTTPException(422, "A meaningful reason is required")
    community = community_for_update(db, community_id, active=False)
    desired = CommunityLifecycleStatus.ACTIVE if approve else CommunityLifecycleStatus.REJECTED
    if community.lifecycle_status == desired:
        return community
    if community.lifecycle_status != CommunityLifecycleStatus.PENDING_REVIEW:
        raise HTTPException(409, "Only pending community applications can be reviewed")

    applicant_id = community.submitted_by_id
    applicant_membership = member_for(db, community_id, applicant_id) if applicant_id else None
    previous = {"lifecycle_status": community.lifecycle_status.value, "is_active": community.is_active}
    community.reviewed_by_id = actor.id
    community.reviewed_at = datetime.now(UTC)
    community.review_reason = reason.strip()
    organization = db.get(Organization, community.organization_id)

    if approve:
        administrator_id = initial_admin_user_id or applicant_id
        if administrator_id is None:
            raise HTTPException(422, "An initial Community Admin is required")
        target = require_verified_admin_candidate(db.get(User, administrator_id))
        admin_membership = member_for(db, community_id, target.id)
        before = state(admin_membership)
        if admin_membership is None:
            admin_membership = Membership(community_id=community_id, user_id=target.id)
            db.add(admin_membership)
        admin_membership.role = MembershipRole.ADMIN
        admin_membership.status = MembershipStatus.ACTIVE
        admin_membership.joined_at = datetime.now(UTC)
        record_membership(db, admin_membership, actor, "admin_assigned", before, reason.strip())
        if applicant_membership and applicant_membership.user_id != target.id:
            applicant_membership.role = MembershipRole.ORGANIZER
            applicant_membership.status = MembershipStatus.ACTIVE
            applicant_membership.joined_at = datetime.now(UTC)
        community.lifecycle_status = CommunityLifecycleStatus.ACTIVE
        community.is_active = True
        if organization:
            organization.is_active = True
            organization.is_verified = True
        action = "approved"
    else:
        community.lifecycle_status = CommunityLifecycleStatus.REJECTED
        community.is_active = False
        if applicant_membership:
            applicant_membership.status = MembershipStatus.DECLINED
        if organization:
            organization.is_active = False
        action = "rejected"

    audit(
        db,
        actor_id=actor.id,
        community_id=community.id,
        action=f"community.{action}",
        target_type="community",
        target_id=community.id,
        metadata={
            "reason": reason.strip(),
            "previous": previous,
            "result": {"lifecycle_status": community.lifecycle_status.value, "is_active": community.is_active},
            "initial_admin_user_id": str(initial_admin_user_id or applicant_id) if approve else None,
        },
        commit=False,
    )
    if applicant_id and applicant_id != actor.id:
        notify(
            db,
            applicant_id,
            f"community_{action}",
            f"Community application {action}",
            f"{community.name}: {reason.strip()}",
            {"community_id": str(community.id)},
            community_id=community.id,
            commit=False,
        )
    db.commit()
    return community


MODERATION_MODELS = {"user": User, "community": Community, "event": Event, "opportunity": ActivityOpportunity, "task": Task}


def moderate(db, actor, kind, target_id, suspend, reason):
    platform_only(actor)
    if len(reason.strip()) < 3:
        raise HTTPException(422, "A meaningful reason is required")
    model = MODERATION_MODELS[kind]
    item = db.scalar(select(model).where(model.id == target_id).with_for_update())
    if item is None:
        raise HTTPException(404, "Moderation target not found")
    if kind == "user" and (item.id == actor.id or item.role == PlatformRole.SUPER_ADMIN):
        raise HTTPException(403, "Super Admin accounts require separate privileged recovery procedures")
    if kind == "user" and suspend:
        administered = db.scalars(select(Membership).where(
            Membership.user_id == item.id,
            Membership.role == MembershipRole.ADMIN,
            Membership.status == MembershipStatus.ACTIVE,
        )).all()
        for membership in administered:
            community = community_for_update(db, membership.community_id, active=False)
            if community and community.lifecycle_status == CommunityLifecycleStatus.ACTIVE:
                removes_final_admin = active_admin_count(db, community.id) <= 1
                removes_final_verified_admin = (
                    item.email_verified_at is not None
                    and active_verified_admin_count(db, community.id) <= 1
                )
                if removes_final_admin or removes_final_verified_admin:
                    raise HTTPException(409, f"Assign another active, verified administrator for {community.name} before suspending this user")
    if kind == "community":
        if item.lifecycle_status in {CommunityLifecycleStatus.DRAFT, CommunityLifecycleStatus.PENDING_REVIEW, CommunityLifecycleStatus.REJECTED}:
            raise HTTPException(409, "Pending or rejected applications must use the review workflow")
        if not suspend and active_verified_admin_count(db, item.id) < 1:
            raise HTTPException(409, "Assign an active, verified Community Admin before restoring this community")
    field = "is_active" if kind in {"user", "community"} else "is_suspended"
    before = getattr(item, field)
    after = not suspend if field == "is_active" else suspend
    if before == after:
        return item
    setattr(item, field, after)
    if kind == "community":
        item.lifecycle_status = (
            CommunityLifecycleStatus.SUSPENDED if suspend else CommunityLifecycleStatus.ACTIVE
        )
    community_id = item.id if kind == "community" else getattr(item, "community_id", None)
    if kind == "user" and suspend:
        for session in db.scalars(select(AuthSession).where(AuthSession.user_id == item.id)):
            session.revoked_at = datetime.now(UTC)
    action = "suspended" if suspend else "restored"
    audit(db, actor_id=actor.id, community_id=community_id, target_type=kind, target_id=item.id,
          action=f"moderation.{action}", metadata={"reason": reason, "previous": {field: before}, "result": {field: after}}, commit=False)
    recipients = set()
    if kind == "user":
        recipients.add(item.id)
    elif kind in {"event", "opportunity", "task"}:
        recipients.add(item.organizer_id if kind == "event" else item.created_by_id)
    if community_id:
        recipients.update(db.scalars(select(Membership.user_id).where(Membership.community_id == community_id,
            Membership.role == MembershipRole.ADMIN, Membership.status == MembershipStatus.ACTIVE)))
    for recipient in recipients:
        notify(db, recipient, "platform_moderation", "Platform moderation update", f"{kind.title()} {action}: {reason}",
               {"target_type": kind, "target_id": str(item.id)}, community_id=community_id, commit=False)
    db.commit()
    return item
