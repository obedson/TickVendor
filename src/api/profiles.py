"""Authenticated profile and journey summary API."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.database import get_db
from src.models import ImpactTransaction, ImpactTransactionStatus, ProfileVisibility, User

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/me")
def my_profile(db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    points = db.scalar(select(func.coalesce(func.sum(ImpactTransaction.points), 0)).where(
        ImpactTransaction.user_id == user.id, ImpactTransaction.status == ImpactTransactionStatus.POSTED
    ))
    return {"id": str(user.id), "username": user.profile.username,
            "display_name": user.profile.display_name, "visibility": user.profile.visibility.value,
            "impact_points": points}


@router.get("/{user_id}")
def public_profile(user_id: UUID, db: Annotated[Session, Depends(get_db)]):
    user = db.get(User, user_id)
    if user is None or user.profile.visibility == ProfileVisibility.PRIVATE:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"username": user.profile.username, "display_name": user.profile.display_name,
            "bio": user.profile.bio, "photo_url": user.profile.photo_url}
