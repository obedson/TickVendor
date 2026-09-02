"""Leaderboard configuration endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.authorization import require_community_role
from src.database import get_db
from src.models import Leaderboard, MembershipRole, User
from src.services.notification import audit

router = APIRouter(prefix="/admin/communities/{community_id}", tags=["admin"])


class LeaderboardInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    metric: str = Field(pattern=r"^(overall|attendance|tasks|service|leadership|event)$")
    period: str = Field(pattern=r"^(all_time|weekly|monthly)$")
    max_entries: int = Field(default=100, ge=1, le=500)
    is_enabled: bool = False


@router.post("/leaderboards", status_code=status.HTTP_201_CREATED)
def create_leaderboard(community_id: UUID, payload: LeaderboardInput,
                       db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    require_community_role(db, community_id, user, MembershipRole.ADMIN)
    board = Leaderboard(community_id=community_id, **payload.model_dump())
    db.add(board); db.flush()
    audit(db, actor_id=user.id, community_id=community_id, action="leaderboard.created", target_type="leaderboard", target_id=board.id, metadata={"metric": board.metric, "period": board.period}, commit=False)
    try: db.commit()
    except IntegrityError as exc: db.rollback(); raise HTTPException(status_code=409, detail="Leaderboard slug already exists") from exc
    return {"id": str(board.id), "slug": board.slug, "is_enabled": board.is_enabled}


@router.patch("/leaderboards/{leaderboard_id}")
def update_leaderboard(community_id: UUID, leaderboard_id: UUID, payload: LeaderboardInput,
                       db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    require_community_role(db, community_id, user, MembershipRole.ADMIN)
    board = db.scalar(select(Leaderboard).where(Leaderboard.id == leaderboard_id, Leaderboard.community_id == community_id))
    if board is None: raise HTTPException(status_code=404, detail="Leaderboard not found")
    values = payload.model_dump()
    for field, value in values.items(): setattr(board, field, value)
    audit(db, actor_id=user.id, community_id=community_id, action="leaderboard.updated", target_type="leaderboard", target_id=board.id, metadata={"fields": sorted(values)}, commit=False)
    db.commit(); return {"id": str(board.id), "slug": board.slug, "is_enabled": board.is_enabled}
