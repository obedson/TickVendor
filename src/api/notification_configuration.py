"""Tenant-scoped notification rule administration."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.authorization import require_community_role
from src.database import get_db
from src.models import MembershipRole, NotificationRule, User
from src.services.notification import audit

router = APIRouter(prefix="/admin/communities/{community_id}/notification-rules", tags=["admin"])


class NotificationRuleInput(BaseModel):
    notification_type: str = Field(min_length=2, max_length=64)
    in_app_enabled: bool = True
    email_enabled: bool = False
    push_enabled: bool = False
    is_active: bool = True


def serialize(rule: NotificationRule) -> dict:
    return {"id": str(rule.id), "notification_type": rule.notification_type,
            "in_app_enabled": rule.in_app_enabled, "email_enabled": rule.email_enabled,
            "push_enabled": rule.push_enabled, "is_active": rule.is_active}


@router.get("")
def list_rules(community_id: UUID, db: Annotated[Session, Depends(get_db)],
               user: Annotated[User, Depends(get_current_user)]):
    require_community_role(db, community_id, user, MembershipRole.ADMIN)
    return [serialize(rule) for rule in db.scalars(select(NotificationRule).where(
        NotificationRule.community_id == community_id).order_by(NotificationRule.notification_type))]


@router.put("")
def upsert_rule(community_id: UUID, payload: NotificationRuleInput,
                db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    require_community_role(db, community_id, user, MembershipRole.ADMIN)
    rule = db.scalar(select(NotificationRule).where(
        NotificationRule.community_id == community_id,
        NotificationRule.notification_type == payload.notification_type,
    ))
    if rule is None:
        rule = NotificationRule(community_id=community_id, notification_type=payload.notification_type)
        db.add(rule)
    for field, value in payload.model_dump().items():
        setattr(rule, field, value)
    db.flush()
    audit(db, actor_id=user.id, community_id=community_id, action="notification_rule.updated",
          target_type="notification_rule", target_id=rule.id,
          metadata={"notification_type": rule.notification_type}, commit=False)
    db.commit()
    return serialize(rule)
