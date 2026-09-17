from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.database import get_db
from src.models import User
from src.models.promotion import Promotion
from src.services import promotion

router = APIRouter(tags=["promotions"])
Surface = Literal["home", "discover", "event-detail", "opportunities", "communities", "tasks"]
Kind = Literal["community", "event", "opportunity", "task"]
DB = Annotated[Session, Depends(get_db)]
Actor = Annotated[User, Depends(get_current_user)]


class PromotionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_type: Kind
    content_id: UUID
    classification: Literal["featured", "sponsored"]
    surface: Surface
    starts_at: datetime
    ends_at: datetime
    priority: int = Field(default=0, ge=-10000, le=10000)
    is_active: bool = False
    reason: str = Field(min_length=3, max_length=1000)

    @model_validator(mode="after")
    def schedule(self):
        if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None:
            raise ValueError("Provide timezone-aware start/end with end after start")
        # Store one UTC instant so a client offset cannot shift the delivery window.
        self.starts_at = self.starts_at.astimezone(UTC)
        self.ends_at = self.ends_at.astimezone(UTC)
        if self.ends_at <= self.starts_at:
            raise ValueError("Provide timezone-aware start/end with end after start")
        if self.content_type == "task" and self.surface not in {"home", "tasks"}:
            raise ValueError("Task placements are limited to authenticated Home and Tasks surfaces")
        return self


@router.get("/promotions/public")
def public(surface: Surface, db: DB, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return promotion.deliver(db, surface)


@router.get("/promotions/me")
def personal(surface: Surface, db: DB, user: Actor, response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    return promotion.deliver(db, surface, user)


@router.get("/admin/promotions/candidates")
def candidates(kind: Kind, db: DB, user: Actor, q: str = "", offset: int = Query(default=0, ge=0)):
    promotion.admin(user)
    model = promotion.CONTENT[kind]
    name = model.name if kind == "community" else model.title
    query = promotion.eligible_query(kind, datetime.now(UTC)).where(name.ilike(f"%{q[:100]}%"))
    return [promotion.serialize_content(kind, item) for item in db.scalars(query.order_by(name, model.id).offset(offset).limit(50))]


@router.get("/admin/promotions")
def listing(db: DB, user: Actor, offset: int = Query(default=0, ge=0)):
    promotion.admin(user)
    return list(db.scalars(select(Promotion).order_by(Promotion.created_at.desc(), Promotion.id).offset(offset).limit(50)))


@router.post("/admin/promotions", status_code=201)
def create(payload: PromotionInput, db: DB, user: Actor):
    return promotion.save(db, user, payload)


@router.put("/admin/promotions/{promotion_id}")
def update(promotion_id: UUID, payload: PromotionInput, db: DB, user: Actor):
    return promotion.save(db, user, payload, promotion_id)


class Deactivate(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


@router.post("/admin/promotions/{promotion_id}/deactivate")
def deactivate(promotion_id: UUID, payload: Deactivate, db: DB, user: Actor):
    promotion.admin(user)
    item = db.get(Promotion, promotion_id)
    if item is None:
        raise HTTPException(404, "Promotion not found")
    item.is_active = False
    promotion.audit(db, actor_id=user.id, action="promotion.deactivated", target_type="promotion", target_id=item.id, metadata={"reason": payload.reason}, commit=False)
    db.commit()
    return {"is_active": False}
