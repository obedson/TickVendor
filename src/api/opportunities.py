"""Activity opportunity discovery and management routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.database import get_db
from src.models import User
from src.schemas.opportunity import (
    OpportunityCreate,
    OpportunityResponse,
    OpportunityUpdate,
    RegistrationResponse,
)
from src.services.opportunity import (
    complete_opportunity,
    create_opportunity,
    get_opportunity,
    get_participant_registration,
    join_opportunity,
    list_opportunities,
    publish_opportunity,
    update_opportunity,
    verify_opportunity,
)

router = APIRouter(tags=["activity opportunities"])


@router.get("/activity-opportunities", response_model=list[OpportunityResponse])
def discover(db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)], community_id: UUID | None = None, offset: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=100)):
    return list_opportunities(db, user, community_id, offset=offset, limit=limit)


@router.get("/communities/{community_id}/activity-opportunities", response_model=list[OpportunityResponse])
def manage_list(community_id: UUID, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    return list_opportunities(db, user, community_id, management=True)


@router.get("/activity-opportunities/{opportunity_id}", response_model=OpportunityResponse)
def detail(opportunity_id: UUID, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    return get_opportunity(db, opportunity_id, user)


@router.post("/communities/{community_id}/activity-opportunities", response_model=OpportunityResponse, status_code=201)
def create(community_id: UUID, payload: OpportunityCreate, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    return create_opportunity(db, community_id, user, **payload.model_dump())


@router.post("/activity-opportunities/{opportunity_id}/publish", response_model=OpportunityResponse)
def publish(opportunity_id: UUID, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    return publish_opportunity(db, opportunity_id, user)


@router.patch("/activity-opportunities/{opportunity_id}", response_model=OpportunityResponse)
def update(opportunity_id: UUID, payload: OpportunityUpdate, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    return update_opportunity(db, opportunity_id, user, **payload.model_dump(exclude_unset=True))


@router.post("/activity-opportunities/{opportunity_id}/join", response_model=RegistrationResponse, status_code=201)
def join(opportunity_id: UUID, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    return join_opportunity(db, opportunity_id, user)


@router.get("/activity-opportunities/{opportunity_id}/registration/me", response_model=RegistrationResponse | None)
def my_registration(opportunity_id: UUID, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    return get_participant_registration(db, opportunity_id, user)


@router.post("/activity-opportunities/{opportunity_id}/complete", response_model=RegistrationResponse)
def complete(opportunity_id: UUID, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    return complete_opportunity(db, opportunity_id, user)


@router.post("/activity-opportunities/{opportunity_id}/registrations/{registration_id}/verify", response_model=RegistrationResponse)
def verify(opportunity_id: UUID, registration_id: UUID, approve: bool, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    return verify_opportunity(db, opportunity_id, registration_id, user, approve)


@router.get("/activity-opportunities/{opportunity_id}/registrations", response_model=list[RegistrationResponse])
def registrations(opportunity_id: UUID, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    from src.services.opportunity import _opportunity
    item = _opportunity(db, opportunity_id)
    from src.authorization import require_community_role
    from src.models import MembershipRole, OpportunityRegistration
    require_community_role(db, item.community_id, user, MembershipRole.ADMIN)
    return db.scalars(select(OpportunityRegistration).where(OpportunityRegistration.opportunity_id == item.id).order_by(OpportunityRegistration.created_at)).all()
