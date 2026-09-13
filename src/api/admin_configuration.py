"""Administrative PointRule and manual adjustment API."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.authorization import require_community_role
from src.database import get_db
from src.models import MembershipRole, PointRule, User
from src.services.admin import adjust_points
from src.services.notification import audit
from src.services.point_policy import ceiling

router = APIRouter(prefix="/admin/communities/{community_id}", tags=["admin"])


class PointRuleInput(BaseModel):
    source_type: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    points: int = Field(ge=-100000, le=100000)
    max_awards_per_user: int | None = Field(default=None, ge=1)
    is_active: bool = True


class PointAdjustmentInput(BaseModel):
    target_user_id: UUID
    amount: int = Field(ge=-100000, le=100000)
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator("amount")
    @classmethod
    def nonzero(cls, value: int) -> int:
        if value == 0:
            raise ValueError("amount must not be zero")
        return value


@router.get("/point-rules")
def list_point_rules(community_id: UUID, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    require_community_role(db, community_id, user, MembershipRole.ADMIN)
    rules = db.scalars(select(PointRule).where((PointRule.community_id == community_id) | PointRule.community_id.is_(None)).order_by(PointRule.source_type)).all()
    return [{"id": str(rule.id), "source_type": rule.source_type, "points": rule.points, "max_awards_per_user": rule.max_awards_per_user, "is_active": rule.is_active, "community_id": str(rule.community_id) if rule.community_id else None} for rule in rules]


@router.put("/point-rules")
def upsert_point_rule(community_id: UUID, payload: PointRuleInput, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    require_community_role(db, community_id, user, MembershipRole.ADMIN)
    rule = db.scalar(select(PointRule).where(PointRule.community_id == community_id, PointRule.source_type == payload.source_type))
    maximum = ceiling(db, payload.source_type)
    if payload.points < 0 or maximum is not None and payload.points > maximum:
        raise HTTPException(422, "Community award must be nonnegative and within the platform maximum")
    if maximum is None and payload.points > 0:
        raise HTTPException(422, "Platform maximum is not configured for this source; ask a Super Admin first")
    previous = {"points": rule.points, "is_active": rule.is_active} if rule else None
    if rule is None: rule = PointRule(community_id=community_id, source_type=payload.source_type); db.add(rule)
    for field, value in payload.model_dump().items(): setattr(rule, field, value)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Point rule conflict; reload and retry") from exc
    audit(db, actor_id=user.id, community_id=community_id, action="point_rule.updated", target_type="point_rule", target_id=rule.id, metadata={"source_type": rule.source_type, "previous": previous, "result": payload.model_dump()}, commit=False)
    try: db.commit()
    except IntegrityError as exc: db.rollback(); raise HTTPException(status_code=409, detail="Point rule conflict") from exc
    return {"id": str(rule.id), "source_type": rule.source_type, "points": rule.points, "is_active": rule.is_active}


@router.post("/point-adjustments")
def manual_adjustment(community_id: UUID, payload: PointAdjustmentInput, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    if db.get(User, payload.target_user_id) is None: raise HTTPException(status_code=404, detail="User not found")
    require_community_role(db, community_id, user, MembershipRole.ADMIN)
    transaction = adjust_points(db, community_id, payload.target_user_id, payload.amount, payload.reason, user)
    return {"id": str(transaction.id), "points": transaction.points, "status": transaction.status.value}
