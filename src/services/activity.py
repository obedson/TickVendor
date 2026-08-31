"""Community activity recording and verification service."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.authorization import require_community_role
from src.models import Activity, ActivityStatus, MembershipRole, User
from src.services.impact import award_points


def record_activity(db: Session, user: User, **values) -> Activity:
    activity = Activity(user_id=user.id, status=ActivityStatus.PENDING, **values)
    db.add(activity)
    db.commit()
    return activity


def verify_activity(db: Session, activity: Activity, verifier: User, approve: bool) -> Activity:
    require_community_role(db, activity.community_id, verifier, MembershipRole.ORGANIZER)
    if activity.status != ActivityStatus.PENDING:
        raise HTTPException(status_code=409, detail="Activity already reviewed")
    activity.status = ActivityStatus.VERIFIED if approve else ActivityStatus.REJECTED
    activity.verified_by_id = verifier.id
    db.commit()
    if approve:
        source_type = f"{activity.dimension.value}_activity"
        award_points(
            db,
            user_id=activity.user_id,
            community_id=activity.community_id,
            source_type=source_type,
            source_id=activity.id,
            idempotency_key=f"activity:{activity.id}:verified",
            reason=f"Verified activity: {activity.activity_type}",
            event_id=activity.event_id,
        )
    return activity
