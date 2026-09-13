"""Google OIDC adapter and conservative, explicit local-account linking."""
import base64
import hashlib
import hmac
from datetime import UTC, datetime
from uuid import uuid4

import httpx
from fastapi import HTTPException
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
from pydantic import EmailStr, TypeAdapter
from sqlalchemy import func, select

from src.config import settings
from src.models import Profile, User
from src.models.external_identity import ExternalIdentity
from src.security import verify_password
from src.services.notification import audit

SUSPENDED = "Your account is suspended. Contact platform support for assistance."
CONFLICT = "We couldn't safely connect this Google account. Sign in using your existing method or contact support."


def challenge(value: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(value.encode()).digest()).rstrip(b"=").decode()


def pkce_verifier(state: str) -> str:
    digest = hmac.new(settings.secret_key.get_secret_value().encode(),
                      b"google-pkce:" + state.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


class BoundedGoogleRequest(GoogleRequest):
    def __call__(self, *args, **kwargs):
        kwargs["timeout"] = 10
        return super().__call__(*args, **kwargs)


def verify_identity(encoded: str, nonce_hash: str) -> dict:
    # Official Google library verifies signature/certificates, exp, iat, aud, issuer.
    claims = id_token.verify_oauth2_token(encoded, BoundedGoogleRequest(), settings.google_client_id)
    if (not isinstance(claims.get("sub"), str) or not 1 <= len(claims["sub"]) <= 255
            or claims.get("email_verified") is not True
            or not hmac.compare_digest(hashlib.sha256(str(claims.get("nonce", "")).encode()).hexdigest(), nonce_hash)
            or claims.get("azp", settings.google_client_id) != settings.google_client_id):
        raise ValueError("Invalid Google identity claims")
    email = str(TypeAdapter(EmailStr).validate_python(claims.get("email"))).lower()
    return {"sub": claims["sub"], "email": email, "name": str(claims.get("name") or "Member")[:120]}


def exchange_code(code: str, state: str, nonce_hash: str) -> dict:
    with httpx.Client(timeout=15, follow_redirects=False) as client:
        response = client.post("https://oauth2.googleapis.com/token", data={
            "code": code, "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret.get_secret_value(),
            "redirect_uri": settings.google_redirect_uri,
            "grant_type": "authorization_code", "code_verifier": pkce_verifier(state),
        })
        if response.status_code != 200:
            raise ValueError("Google exchange failed")
        return verify_identity(response.json()["id_token"], nonce_hash)


def resolve_identity(db, flow, password=None):
    identity = db.scalar(select(ExternalIdentity).where(
        ExternalIdentity.provider == "google", ExternalIdentity.provider_subject == flow.provider_subject))
    if identity:
        user = db.scalar(select(User).where(User.id == identity.user_id).with_for_update())
        if not user.is_active:
            raise HTTPException(403, SUSPENDED)
        # Subject is stable; do not overwrite the local email or merge on changed email.
        identity.provider_email = flow.provider_email
        return user
    matches = list(db.scalars(select(User).where(func.lower(User.email) == flow.provider_email).with_for_update()))
    if len(matches) > 1:
        raise HTTPException(409, CONFLICT)
    user = matches[0] if matches else None
    if user:
        if db.scalar(select(ExternalIdentity).where(ExternalIdentity.user_id == user.id,
                                                   ExternalIdentity.provider == "google")):
            raise HTTPException(409, CONFLICT)
        if not user.password_hash:
            raise HTTPException(409, CONFLICT)
        if password is None:
            raise HTTPException(409, "Confirm your existing TickVendor password to link Google.")
        if not verify_password(password, user.password_hash):
            raise HTTPException(401, "Unable to confirm account ownership.")
        if not user.is_active:
            raise HTTPException(403, SUSPENDED)
    else:
        user = User(email=flow.provider_email, password_hash=None)
        user.profile = Profile(username=f"member_{uuid4().hex[:24]}", display_name=flow.provider_name or "Member")
        db.add(user); db.flush()
    # Exact same email verified by Google; linking also required existing local proof.
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(UTC)
    db.add(ExternalIdentity(user_id=user.id, provider="google", provider_subject=flow.provider_subject,
                            provider_email=flow.provider_email))
    audit(db, actor_id=user.id, action="auth.external_identity_linked", target_type="user", target_id=user.id,
          metadata={"provider": "google"}, commit=False)
    return user
