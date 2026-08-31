"""Authentication API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from src.config import settings
from src.database import get_db
from src.models import Profile, User
from src.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from src.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")


def serialize_user(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        role=user.role.value,
        username=user.profile.username,
        display_name=user.profile.display_name,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    user = User(email=str(payload.email), password_hash=hash_password(payload.password))
    user.profile = Profile(username=payload.username, display_name=payload.display_name)
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email or username is already registered") from exc
    db.refresh(user)
    return TokenResponse(
        access_token=create_access_token(user.id, user.role.value), user=serialize_user(user)
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    user = db.scalar(
        select(User).options(selectinload(User.profile)).where(User.email == str(payload.email))
    )
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenResponse(
        access_token=create_access_token(user.id, user.role.value), user=serialize_user(user)
    )


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], db: Annotated[Session, Depends(get_db)]
) -> User:
    try:
        payload = decode_access_token(token)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    user = db.scalar(
        select(User).options(selectinload(User.profile)).where(User.id == payload["sub"])
    )
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User is unavailable")
    return user


@router.get("/me", response_model=UserResponse)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return serialize_user(current_user)
