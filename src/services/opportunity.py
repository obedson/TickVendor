"""Tenant-scoped activity opportunity lifecycle."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.authorization import require_community_role
from src.models import (
    Activity,
    ActivityOpportunity,
    ActivityStatus,
    EngagementDimension,
    Membership,
    MembershipRole,
    MembershipStatus,
    OpportunityRegistration,
    OpportunityRegistrationStatus,
    OpportunityStatus,
    User,
)
from src.services.activity import verify_activity
from src.services.notification import audit, notify


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _opportunity(db: Session, opportunity_id: UUID) -> ActivityOpportunity:
    item = db.get(ActivityOpportunity, opportunity_id)
    if item is None or item.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return item


def create_opportunity(db: Session, community_id: UUID, user: User, **values) -> ActivityOpportunity:
    require_community_role(db, community_id, user, MembershipRole.ADMIN)
    if values["ends_at"] <= values["starts_at"]:
        raise HTTPException(status_code=422, detail="ends_at must be after starts_at")
    item = ActivityOpportunity(community_id=community_id, created_by_id=user.id, **values)
    db.add(item); db.commit(); db.refresh(item)
    audit(db, actor_id=user.id, community_id=community_id, action="activity_opportunity.created", target_type="activity_opportunity", target_id=item.id, metadata={"title": item.title})
    return item


def publish_opportunity(db: Session, opportunity_id: UUID, user: User) -> ActivityOpportunity:
    item = _opportunity(db, opportunity_id)
    require_community_role(db, item.community_id, user, MembershipRole.ADMIN)
    if item.status != OpportunityStatus.DRAFT:
        raise HTTPException(status_code=409, detail="Only draft opportunities can be published")
    if _as_utc(item.ends_at) <= datetime.now(UTC):
        raise HTTPException(status_code=409, detail="Past opportunities cannot be published")
    item.status = OpportunityStatus.PUBLISHED; db.commit()
    audit(db, actor_id=user.id, community_id=item.community_id, action="activity_opportunity.published", target_type="activity_opportunity", target_id=item.id)
    return item


def update_opportunity(db: Session, opportunity_id: UUID, user: User, **values) -> ActivityOpportunity:
    item = _opportunity(db, opportunity_id)
    require_community_role(db, item.community_id, user, MembershipRole.ADMIN)
    if item.status != OpportunityStatus.DRAFT:
        raise HTTPException(status_code=409, detail="Only draft opportunities can be edited")
    for field, value in values.items():
        if value is not None:
            setattr(item, field, value)
    if _as_utc(item.ends_at) <= _as_utc(item.starts_at):
        raise HTTPException(status_code=422, detail="ends_at must be after starts_at")
    db.commit(); db.refresh(item)
    audit(db, actor_id=user.id, community_id=item.community_id, action="activity_opportunity.updated", target_type="activity_opportunity", target_id=item.id, metadata={"fields": sorted(values)})
    return item


def list_opportunities(db: Session, user: User, community_id: UUID | None = None, management: bool = False):
    if management:
        if community_id is None: raise HTTPException(status_code=422, detail="community_id is required")
        require_community_role(db, community_id, user, MembershipRole.ADMIN)
        query = select(ActivityOpportunity).where(ActivityOpportunity.community_id == community_id, ActivityOpportunity.deleted_at.is_(None))
    else:
        query = select(ActivityOpportunity).outerjoin(
            Membership,
            (Membership.community_id == ActivityOpportunity.community_id)
            & (Membership.user_id == user.id)
            & (Membership.status == MembershipStatus.ACTIVE),
        ).where(
            ActivityOpportunity.status == OpportunityStatus.PUBLISHED,
            ActivityOpportunity.deleted_at.is_(None),
            ActivityOpportunity.ends_at >= datetime.now(UTC),
            (ActivityOpportunity.members_only.is_(False) | (Membership.id.is_not(None))),
        )
    return list(db.scalars(query.order_by(ActivityOpportunity.starts_at, ActivityOpportunity.id).limit(100)))


def join_opportunity(db: Session, opportunity_id: UUID, user: User) -> OpportunityRegistration:
    item = _opportunity(db, opportunity_id)
    if item.status != OpportunityStatus.PUBLISHED or _as_utc(item.ends_at) < datetime.now(UTC):
        raise HTTPException(status_code=409, detail="Opportunity is not open for registration")
    if item.members_only:
        require_community_role(db, item.community_id, user)
    existing = db.scalar(select(OpportunityRegistration).where(OpportunityRegistration.opportunity_id == item.id, OpportunityRegistration.participant_id == user.id))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Already registered for this opportunity")
    if item.capacity is not None and db.scalar(select(func.count()).select_from(OpportunityRegistration).where(OpportunityRegistration.opportunity_id == item.id, OpportunityRegistration.status == OpportunityRegistrationStatus.REGISTERED)) >= item.capacity:
        raise HTTPException(status_code=409, detail="Opportunity is at capacity")
    registration = OpportunityRegistration(opportunity_id=item.id, participant_id=user.id)
    db.add(registration); db.commit(); db.refresh(registration)
    audit(db, actor_id=user.id, community_id=item.community_id, action="activity_opportunity.joined",
          target_type="opportunity_registration", target_id=registration.id,
          metadata={"opportunity_id": str(item.id)})
    notify(db, user.id, "opportunity_registered", "Opportunity registration confirmed",
           f"You registered for {item.title}.", {"opportunity_id": str(item.id)},
           community_id=item.community_id,
           deduplication_key=f"opportunity:{item.id}:participant:{user.id}:registered")
    return registration


def get_participant_registration(db: Session, opportunity_id: UUID, user: User) -> OpportunityRegistration | None:
    _opportunity(db, opportunity_id)
    return db.scalar(select(OpportunityRegistration).where(
        OpportunityRegistration.opportunity_id == opportunity_id,
        OpportunityRegistration.participant_id == user.id,
    ))


def complete_opportunity(db: Session, opportunity_id: UUID, user: User) -> OpportunityRegistration:
    item = _opportunity(db, opportunity_id)
    registration = db.scalar(select(OpportunityRegistration).where(OpportunityRegistration.opportunity_id == item.id, OpportunityRegistration.participant_id == user.id))
    if registration is None:
        raise HTTPException(status_code=404, detail="Registration not found")
    if registration.status != OpportunityRegistrationStatus.REGISTERED:
        raise HTTPException(status_code=409, detail="Registration cannot be completed in its current state")
    registration.status = OpportunityRegistrationStatus.COMPLETED
    registration.completed_at = datetime.now(UTC)
    db.add(Activity(community_id=item.community_id, opportunity_id=item.id, user_id=user.id, activity_type=item.activity_type, dimension=EngagementDimension(item.dimension), description=item.description, status=ActivityStatus.PENDING, occurred_at=registration.completed_at))
    db.commit(); db.refresh(registration)
    audit(db, actor_id=user.id, community_id=item.community_id, action="activity_opportunity.completed",
          target_type="opportunity_registration", target_id=registration.id,
          metadata={"opportunity_id": str(item.id)})
    notify(db, user.id, "opportunity_completed", "Opportunity marked complete",
           f"Your participation in {item.title} is awaiting verification.",
           {"opportunity_id": str(item.id)}, community_id=item.community_id,
           deduplication_key=f"opportunity:{item.id}:participant:{user.id}:completed")
    return registration


def verify_opportunity(db: Session, opportunity_id: UUID, registration_id: UUID, user: User, approve: bool) -> OpportunityRegistration:
    item = _opportunity(db, opportunity_id)
    require_community_role(db, item.community_id, user, MembershipRole.ADMIN)
    registration = db.scalar(select(OpportunityRegistration).where(OpportunityRegistration.id == registration_id, OpportunityRegistration.opportunity_id == item.id))
    if registration is None:
        raise HTTPException(status_code=404, detail="Registration not found")
    if registration.status != OpportunityRegistrationStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="Only completed registrations can be verified")
    registration.status = OpportunityRegistrationStatus.VERIFIED if approve else OpportunityRegistrationStatus.REJECTED
    registration.verified_by_id = user.id; registration.verified_at = datetime.now(UTC)
    activity = db.scalar(select(Activity).where(Activity.opportunity_id == item.id, Activity.user_id == registration.participant_id, Activity.status == ActivityStatus.PENDING).order_by(Activity.created_at.desc()))
    if activity is not None:
        verify_activity(db, activity, user, approve)
    db.commit(); db.refresh(registration)
    audit(db, actor_id=user.id, community_id=item.community_id, action="activity_opportunity.verified" if approve else "activity_opportunity.rejected", target_type="activity_opportunity", target_id=item.id, metadata={"registration_id": str(registration.id)})
    return registration
