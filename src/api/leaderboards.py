"""Tenant-authorized leaderboard API."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.authorization import require_community_role
from src.database import get_db
from src.models import Leaderboard, MembershipRole, User
from src.services.leaderboard import leaderboard_entries

router = APIRouter(prefix="/leaderboards", tags=["leaderboards"])


@router.get("/{community_id}")
def community_leaderboard(
    community_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    leaderboard_id: UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
):
    require_community_role(db, community_id, user, MembershipRole.MEMBER)
    query = select(Leaderboard).where(Leaderboard.community_id == community_id)
    if leaderboard_id is not None: query = query.where(Leaderboard.id == leaderboard_id)
    leaderboard = db.scalar(query.order_by(Leaderboard.created_at))
    if leaderboard is None: raise HTTPException(status_code=404, detail="Leaderboard not found")
    return {"id": str(leaderboard.id), "name": leaderboard.name, "metric": leaderboard.metric,
            "period": leaderboard.period, "entries": leaderboard_entries(db, leaderboard, user, limit)}
