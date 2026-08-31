"""Community analytics API."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.database import get_db
from src.models import User
from src.services.analytics import community_summary

router = APIRouter(prefix="/communities", tags=["communities"])


@router.get("/{community_id}/analytics")
def analytics(
    community_id: UUID, db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    return community_summary(db, community_id, user)
