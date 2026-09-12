"""No participant evidence-deletion endpoint is exposed."""
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.database import get_db
from src.models import PersonalArchive, User
from src.services.personal_archive import personal_items, set_archive

router = APIRouter(prefix="/me", tags=["personal presentation"])
DB = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
Kind = Literal["notification", "ticket", "task", "opportunity"]


@router.get("/archive")
def archives(db: DB, user: CurrentUser):
    return [{"item_type": item.item_type, "item_id": str(item.item_id)} for item in db.scalars(
        select(PersonalArchive).where(PersonalArchive.user_id == user.id))]


@router.get("/personal-items/{kind}")
def items(kind: Kind, db: DB, user: CurrentUser, offset: int = Query(0, ge=0)):
    return personal_items(db, user, kind, offset)


@router.post("/archive/{kind}/{item_id}", status_code=204)
def archive(kind: Kind, item_id: UUID, db: DB, user: CurrentUser):
    set_archive(db, user, kind, item_id, True)
    return Response(status_code=204)


@router.delete("/archive/{kind}/{item_id}", status_code=204)
def unarchive(kind: Kind, item_id: UUID, db: DB, user: CurrentUser):
    set_archive(db, user, kind, item_id, False)
    return Response(status_code=204)
