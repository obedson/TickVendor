"""Authorization-code OIDC with browser-bound state and a PKCE-bound SPA handoff."""
import hmac
from datetime import UTC, datetime, timedelta
from typing import Annotated
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.auth import issue_tokens
from src.config import settings
from src.database import get_db
from src.models.external_identity import GoogleAuthFlow
from src.monitoring import emit
from src.schemas.auth import TokenResponse
from src.security import create_opaque_token, hash_token
from src.security_middleware import auth_rate_limit
from src.services import google_identity

router = APIRouter(prefix="/auth/google", tags=["auth"], dependencies=[Depends(auth_rate_limit)])
DB = Annotated[Session, Depends(get_db)]
COOKIE = "tickvendor_google_state"


def configured():
    if not (settings.google_auth_enabled and settings.google_client_id and settings.google_client_secret
            and settings.google_redirect_uri):
        return False
    redirect = urlsplit(settings.google_redirect_uri)
    frontend = urlsplit(settings.frontend_url or settings.canonical_url)
    local = settings.environment in {"development", "test"}
    return redirect.path == settings.api_v1_prefix + "/auth/google/callback" and frontend.path in {"", "/"} and all(u.hostname and (u.scheme == "https" or local and u.scheme == "http" and u.hostname in {"localhost", "127.0.0.1"})
               for u in (redirect, frontend)) and not any(u.query or u.fragment or u.username for u in (redirect, frontend))


def require_config():
    if not configured():
        raise HTTPException(503, "Google sign-in is not configured. Use email and password.")


def finish(**values):
    # Fixed configured frontend only; never accept a caller-supplied return URL.
    response = RedirectResponse((settings.frontend_url or settings.canonical_url).rstrip("/")
                                + "/auth/google/return#" + urlencode(values), status_code=303)
    response.delete_cookie(COOKIE, path=settings.api_v1_prefix + "/auth/google")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.get("/config")
def config():
    return {"enabled": bool(configured())}


@router.get("/start")
def start(db: DB, handoff_challenge: Annotated[str, Query(pattern=r"^[A-Za-z0-9_-]{43}$")]):
    require_config()
    now = datetime.now(UTC)
    db.execute(delete(GoogleAuthFlow).where(GoogleAuthFlow.expires_at < now))
    state, browser, nonce = create_opaque_token(), create_opaque_token(), create_opaque_token()
    db.add(GoogleAuthFlow(state_hash=hash_token(state), browser_hash=hash_token(browser),
                         nonce_hash=hash_token(nonce), handoff_challenge=handoff_challenge,
                         expires_at=now + timedelta(minutes=10)))
    db.commit()
    params = {"client_id": settings.google_client_id, "redirect_uri": settings.google_redirect_uri,
              "response_type": "code", "scope": "openid email profile", "state": state, "nonce": nonce,
              "code_challenge": google_identity.challenge(google_identity.pkce_verifier(state)),
              "code_challenge_method": "S256", "prompt": "select_account"}
    response = RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params), status_code=303)
    response.set_cookie(COOKIE, browser, max_age=600, httponly=True, samesite="lax",
                        secure=settings.google_redirect_uri.startswith("https://"),
                        path=settings.api_v1_prefix + "/auth/google")
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/callback")
def callback(request: Request, db: DB, state: str = "", code: str = "", error: str = ""):
    if not configured():
        return finish(error="unavailable")
    now = datetime.now(UTC)
    if not 32 <= len(state) <= 256:
        return finish(error="invalid_state")
    flow = db.scalar(select(GoogleAuthFlow).where(GoogleAuthFlow.state_hash == hash_token(state)))
    browser = request.cookies.get(COOKIE, "")
    if not flow or not browser or not hmac.compare_digest(flow.browser_hash, hash_token(browser)):
        return finish(error="invalid_state")
    consumed = db.execute(update(GoogleAuthFlow).where(
        GoogleAuthFlow.id == flow.id, GoogleAuthFlow.callback_at.is_(None), GoogleAuthFlow.expires_at > now
    ).values(callback_at=now).execution_options(synchronize_session=False))
    db.commit()
    if consumed.rowcount != 1:
        return finish(error="invalid_state")
    if error:
        return finish(error="cancelled" if error == "access_denied" else "provider_denied")
    if not code or len(code) > 4096:
        return finish(error="provider_failure")
    try:
        claims = google_identity.exchange_code(code, state, flow.nonce_hash)
    except Exception:  # noqa: BLE001 -- fail closed without logging provider secrets
        # Never log provider exceptions: they may contain authorization codes/tokens.
        emit("authentication_failure", reason="google_verification_failed")
        return finish(error="provider_failure")
    flow.provider_subject, flow.provider_email, flow.provider_name = claims["sub"], claims["email"], claims["name"]
    grant = create_opaque_token()
    flow.handoff_hash = hash_token(grant)
    flow.expires_at = datetime.now(UTC) + timedelta(minutes=2)
    db.commit()
    # Opaque single-use grant, not a Google or TickVendor token; bound to SPA proof.
    return finish(grant=grant)


class CompleteInput(BaseModel):
    grant: str = Field(min_length=32, max_length=256)
    verifier: str = Field(min_length=43, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    password: str | None = Field(default=None, min_length=1, max_length=72)


@router.post("/complete", response_model=TokenResponse)
def complete(payload: CompleteInput, db: DB):
    require_config()
    now = datetime.now(UTC)
    flow = db.scalar(select(GoogleAuthFlow).where(
        GoogleAuthFlow.handoff_hash == hash_token(payload.grant), GoogleAuthFlow.consumed_at.is_(None),
        GoogleAuthFlow.expires_at > now).with_for_update())
    if (flow is None or not flow.provider_subject or flow.link_failures >= 5
            or not hmac.compare_digest(flow.handoff_challenge, google_identity.challenge(payload.verifier))):
        raise HTTPException(400, "Google sign-in expired or is invalid. Please start again.")
    try:
        user = google_identity.resolve_identity(db, flow, payload.password)
        claimed = db.execute(update(GoogleAuthFlow).where(GoogleAuthFlow.id == flow.id,
            GoogleAuthFlow.consumed_at.is_(None), GoogleAuthFlow.expires_at > now
        ).values(consumed_at=now).execution_options(synchronize_session=False))
        if claimed.rowcount != 1:
            db.rollback()
            raise HTTPException(400, "Google sign-in expired or is invalid. Please start again.")
        response = issue_tokens(db, user)
        db.commit()
    except HTTPException:
        if payload.password is not None:
            flow.link_failures += 1
            db.commit()
        emit("authentication_failure", reason="google_link_or_status_rejected")
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, google_identity.CONFLICT) from exc
    return response
