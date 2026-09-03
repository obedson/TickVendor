"""Authentication API routes and revocable session lifecycle."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from src.config import settings
from src.database import get_db
from src.models import AuthSession, AuthToken, AuthTokenPurpose, Profile, User
from src.monitoring import emit
from src.notifications.email import EmailSender, get_email_sender
from src.schemas.auth import (
    LoginRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    TokenRequest,
    TokenResponse,
    UserResponse,
)
from src.security import (
    InvalidTokenError,
    create_access_token,
    create_opaque_token,
    decode_access_token,
    hash_password,
    hash_token,
    verify_password,
)
from src.security_middleware import login_attempt_limiter

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")


def serialize_user(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id), email=user.email, role=user.role.value,
        username=user.profile.username, display_name=user.profile.display_name,
    )


def create_refresh_session(db: Session, user: User) -> str:
    token = create_opaque_token()
    db.add(AuthSession(
        user_id=user.id, token_hash=hash_token(token),
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
    ))
    return token


def issue_tokens(db: Session, user: User) -> TokenResponse:
    refresh_token = create_refresh_session(db, user)
    return TokenResponse(
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=refresh_token,
        user=serialize_user(user),
    )


def create_one_time_token(db: Session, user: User, purpose: AuthTokenPurpose, hours: int) -> str:
    token = create_opaque_token()
    db.add(AuthToken(
        user_id=user.id, purpose=purpose, token_hash=hash_token(token),
        expires_at=datetime.now(UTC) + timedelta(hours=hours),
    ))
    return token


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
    email_sender: Annotated[EmailSender, Depends(get_email_sender)],
) -> TokenResponse:
    user = User(email=str(payload.email), password_hash=hash_password(payload.password))
    user.profile = Profile(username=payload.username, display_name=payload.display_name)
    db.add(user)
    try:
        db.flush()
        verification_token = create_one_time_token(
            db, user, AuthTokenPurpose.EMAIL_VERIFICATION, hours=24
        )
        response = issue_tokens(db, user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email or username is already registered") from exc
    email_sender.send_token(user.email, "Verify your TickVendor email", verification_token)
    return response


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest, request: Request, db: Annotated[Session, Depends(get_db)]
) -> TokenResponse:
    host = request.client.host if request.client else "unknown"
    attempt_key = f"{host}:{str(payload.email).lower()}"
    login_attempt_limiter.check(attempt_key)
    user = db.scalar(select(User).options(selectinload(User.profile)).where(User.email == str(payload.email)))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        login_attempt_limiter.record_failure(attempt_key)
        emit("authentication_failure", reason="invalid_credentials")
        raise HTTPException(status_code=401, detail="Invalid email or password")
    login_attempt_limiter.record_success(attempt_key)
    response = issue_tokens(db, user)
    db.commit()
    return response


@router.post("/verify-email", status_code=204)
def verify_email(payload: TokenRequest, db: Annotated[Session, Depends(get_db)]) -> Response:
    token = db.scalar(select(AuthToken).where(
        AuthToken.token_hash == hash_token(payload.token),
        AuthToken.purpose == AuthTokenPurpose.EMAIL_VERIFICATION,
        AuthToken.consumed_at.is_(None), AuthToken.expires_at > datetime.now(UTC),
    ))
    if token is None:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    user = db.get(User, token.user_id)
    user.email_verified_at = datetime.now(UTC)
    token.consumed_at = datetime.now(UTC)
    db.commit()
    return Response(status_code=204)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    session = db.scalar(select(AuthSession).where(
        AuthSession.token_hash == hash_token(payload.refresh_token),
        AuthSession.revoked_at.is_(None), AuthSession.expires_at > datetime.now(UTC),
    ))
    if session is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    user = db.scalar(select(User).options(selectinload(User.profile)).where(User.id == session.user_id))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User is unavailable")
    response = issue_tokens(db, user)
    db.flush()
    replacement = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(response.refresh_token)))
    session.revoked_at = datetime.now(UTC)
    session.replaced_by_id = replacement.id
    db.commit()
    return response


@router.post("/logout", status_code=204)
def logout(payload: RefreshRequest, db: Annotated[Session, Depends(get_db)]) -> Response:
    db.execute(update(AuthSession).where(
        AuthSession.token_hash == hash_token(payload.refresh_token), AuthSession.revoked_at.is_(None)
    ).values(revoked_at=datetime.now(UTC)))
    db.commit()
    return Response(status_code=204)


@router.post("/password-reset/request", status_code=202)
def request_password_reset(
    payload: PasswordResetRequest,
    db: Annotated[Session, Depends(get_db)],
    email_sender: Annotated[EmailSender, Depends(get_email_sender)],
) -> dict[str, str]:
    user = db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user is not None and user.is_active:
        token = create_one_time_token(db, user, AuthTokenPurpose.PASSWORD_RESET, hours=1)
        db.commit()
        email_sender.send_token(user.email, "Reset your TickVendor password", token)
    return {"message": "If the account exists, reset instructions were sent."}


@router.post("/password-reset/confirm", status_code=204)
def confirm_password_reset(
    payload: PasswordResetConfirmRequest, db: Annotated[Session, Depends(get_db)]
) -> Response:
    token = db.scalar(select(AuthToken).where(
        AuthToken.token_hash == hash_token(payload.token),
        AuthToken.purpose == AuthTokenPurpose.PASSWORD_RESET,
        AuthToken.consumed_at.is_(None), AuthToken.expires_at > datetime.now(UTC),
    ))
    if token is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    user = db.get(User, token.user_id)
    user.password_hash = hash_password(payload.new_password)
    token.consumed_at = datetime.now(UTC)
    db.execute(update(AuthSession).where(
        AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)
    ).values(revoked_at=datetime.now(UTC)))
    db.commit()
    return Response(status_code=204)


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], db: Annotated[Session, Depends(get_db)]
) -> User:
    try:
        payload = decode_access_token(token)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    user = db.scalar(select(User).options(selectinload(User.profile)).where(User.id == payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User is unavailable")
    return user


@router.get("/me", response_model=UserResponse)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return serialize_user(current_user)
