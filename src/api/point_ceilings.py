"""Super Admin ceiling configuration; authenticated read for guidance."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.database import get_db
from src.models import PointCeiling, User
from src.services.governance import platform_only
from src.services.notification import audit

router = APIRouter(prefix="/point-ceilings", tags=["point governance"])
DB = Annotated[Session, Depends(get_db)]
Current = Annotated[User, Depends(get_current_user)]


class CeilingInput(BaseModel):
    source_type: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    maximum_points: int = Field(ge=0, le=100000)
    reason: str = Field(min_length=3, max_length=1000)


    @field_validator("reason")
    @classmethod
    def meaningful_reason(cls, value):
        if len(value.strip()) < 3:
            raise ValueError("Provide a meaningful reason")
        return value.strip()


@router.get("")
def list_ceilings(db: DB, user: Current):
    return [{"source_type": item.source_type, "maximum_points": item.maximum_points}
            for item in db.scalars(select(PointCeiling).order_by(PointCeiling.source_type))]


@router.put("")
def save_ceiling(payload: CeilingInput, db: DB, user: Current):
    platform_only(user)
    # Existing rows serialize updates; the unique source index rejects creation races.
    item = db.scalar(select(PointCeiling).where(PointCeiling.source_type == payload.source_type).with_for_update())
    previous = item.maximum_points if item else None
    if item is None:
        item = PointCeiling(source_type=payload.source_type)
        db.add(item)
    item.maximum_points = payload.maximum_points
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Point ceiling changed concurrently; reload and retry") from exc
    audit(db, actor_id=user.id, action="point_ceiling.updated", target_type="point_ceiling", target_id=item.id,
          metadata={"reason": payload.reason, "previous": previous, "maximum_points": item.maximum_points, "source_type": item.source_type}, commit=False)
    db.commit()
    return {"source_type": item.source_type, "maximum_points": item.maximum_points}
