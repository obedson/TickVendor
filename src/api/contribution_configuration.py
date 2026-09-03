"""Contribution reward-band administration."""

from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.authorization import require_community_role
from src.database import get_db
from src.models import ContributionBand, MembershipRole, User
from src.services.notification import audit

router = APIRouter(prefix="/admin/communities/{community_id}", tags=["admin"])

@router.get("/contribution-bands")
def list_bands(community_id: UUID, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    require_community_role(db, community_id, user, MembershipRole.ADMIN)
    return [{"id": str(band.id), "currency": band.currency, "minimum_amount": str(band.minimum_amount), "maximum_amount": str(band.maximum_amount) if band.maximum_amount is not None else None, "points": band.points, "per_user_period_cap": band.per_user_period_cap, "is_active": band.is_active} for band in db.scalars(select(ContributionBand).where(ContributionBand.community_id == community_id).order_by(ContributionBand.minimum_amount, ContributionBand.id))]


class ContributionBandInput(BaseModel):
    currency: str = Field(default="NGN", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    minimum_amount: Decimal = Field(ge=0)
    maximum_amount: Decimal | None = Field(default=None, ge=0)
    points: int = Field(ge=0, le=100000)
    per_user_period_cap: int | None = Field(default=None, ge=1, le=1000000)
    is_active: bool = True

    @model_validator(mode="after")
    def valid_range(self):
        if self.maximum_amount is not None and self.maximum_amount < self.minimum_amount:
            raise ValueError("maximum must be greater than or equal to minimum")
        return self


@router.post("/contribution-bands", status_code=status.HTTP_201_CREATED)
def create_band(community_id: UUID, payload: ContributionBandInput,
                db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    require_community_role(db, community_id, user, MembershipRole.ADMIN)
    overlap = db.scalar(select(ContributionBand).where(
        ContributionBand.community_id == community_id, ContributionBand.currency == payload.currency,
        ContributionBand.is_active.is_(True), ContributionBand.minimum_amount <= (payload.maximum_amount or payload.minimum_amount),
        (ContributionBand.maximum_amount.is_(None)) | (ContributionBand.maximum_amount >= payload.minimum_amount),
    ))
    if overlap: raise HTTPException(status_code=409, detail="Contribution band overlaps an active band")
    band = ContributionBand(community_id=community_id, **payload.model_dump()); db.add(band); db.flush()
    audit(db, actor_id=user.id, community_id=community_id, action="contribution_band.created", target_type="contribution_band", target_id=band.id, metadata={"currency": band.currency}, commit=False)
    db.commit(); return {"id": str(band.id), "currency": band.currency, "minimum_amount": str(band.minimum_amount), "points": band.points, "is_active": band.is_active}


@router.patch("/contribution-bands/{band_id}")
def update_band(community_id: UUID, band_id: UUID, payload: ContributionBandInput,
                db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    require_community_role(db, community_id, user, MembershipRole.ADMIN)
    band = db.scalar(select(ContributionBand).where(ContributionBand.id == band_id, ContributionBand.community_id == community_id))
    if band is None: raise HTTPException(status_code=404, detail="Contribution band not found")
    for field, value in payload.model_dump().items(): setattr(band, field, value)
    audit(db, actor_id=user.id, community_id=community_id, action="contribution_band.updated", target_type="contribution_band", target_id=band.id, metadata={"fields": sorted(payload.model_dump())}, commit=False)
    db.commit(); return {"id": str(band.id), "points": band.points, "is_active": band.is_active}
