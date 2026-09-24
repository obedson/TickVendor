"""Deterministic provider boundaries and real local auth/session integration."""
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config import settings
from src.models import User
from src.models.external_identity import ExternalIdentity, GoogleAuthFlow
from src.notifications.email import InMemoryEmailSender, get_email_sender
from src.security import hash_token
from src.security_middleware import RateLimiter
from src.services import google_identity
from tests.test_auth import make_client


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'google_auth_enabled', True)
    monkeypatch.setattr(settings, 'google_client_id', 'test-client')
    monkeypatch.setattr(settings, 'google_client_secret', SecretStr('test-only-secret'))
    monkeypatch.setattr(settings, 'google_redirect_uri', 'http://localhost:8000/api/v1/auth/google/callback')
    monkeypatch.setattr(settings, 'frontend_url', 'http://localhost:5173')
    monkeypatch.setattr(settings, 'environment', 'test')
    monkeypatch.setattr('src.security_middleware.auth_rate_limiter', RateLimiter(limit=1000))
    monkeypatch.setattr('src.main.rate_limiter', RateLimiter(limit=1000))
    client, engine = make_client(tmp_path)
    sender = InMemoryEmailSender()
    client.app.dependency_overrides[get_email_sender] = lambda: sender
    yield client, engine, sender
    client.close()
    engine.dispose()


def register(client):
    response = client.post('/api/v1/auth/register', json={
        'email': 'member@example.com', 'password': 'initial-password-123',
        'username': 'member', 'display_name': 'Member'})
    assert response.status_code == 201, response.text
    return response.json()


def grant(client, monkeypatch, subject='google-subject', email='member@example.com'):
    verifier = 'a' * 64
    response = client.get('/api/v1/auth/google/start', params={
        'handoff_challenge': google_identity.challenge(verifier)}, follow_redirects=False)
    assert response.status_code == 303, response.text
    params = parse_qs(urlsplit(response.headers['location']).query)
    assert params['code_challenge_method'] == ['S256']
    assert params['scope'] == ['openid email profile']
    monkeypatch.setattr(google_identity, 'exchange_code', lambda *_: {'sub': subject, 'email': email, 'name': 'Google Member'})
    response = client.get('/api/v1/auth/google/callback', params={'state': params['state'][0], 'code': 'test-code'}, follow_redirects=False)
    assert response.status_code == 303
    return {'grant': parse_qs(urlsplit(response.headers['location']).fragment)['grant'][0], 'verifier': verifier}


def test_new_google_user_normal_sessions_and_replay(env, monkeypatch):
    client, engine, sender = env
    payload = grant(client, monkeypatch)
    bad = client.post('/api/v1/auth/google/complete', json={**payload, 'verifier': 'b' * 64})
    assert bad.status_code == 400
    response = client.post('/api/v1/auth/google/complete', json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    with Session(engine) as db:
        user = db.scalar(select(User))
        assert user.password_hash is None and user.email_verified_at is not None
        assert db.scalar(select(func.count()).select_from(ExternalIdentity)) == 1
    assert not sender.messages
    assert client.post('/api/v1/auth/google/complete', json=payload).status_code == 400
    assert client.get('/api/v1/auth/me', headers={'Authorization': 'Bearer ' + body['access_token']}).status_code == 200
    rotated = client.post('/api/v1/auth/refresh', json={'refresh_token': body['refresh_token']})
    assert rotated.status_code == 200
    assert client.post('/api/v1/auth/refresh', json={'refresh_token': body['refresh_token']}).status_code == 401
    token = rotated.json()['refresh_token']
    assert client.post('/api/v1/auth/logout', json={'refresh_token': token}).status_code == 204
    assert client.post('/api/v1/auth/refresh', json={'refresh_token': token}).status_code == 401


def test_existing_account_requires_password_and_preserves_identity(env, monkeypatch):
    from src.models import Community, Membership, MembershipRole, Organization, PlatformRole

    client, engine, _ = env
    original = register(client)
    with Session(engine) as db:
        user = db.scalar(select(User)); user.role = PlatformRole.PARTICIPANT
        org = Organization(owner_id=user.id, name='Original organization', slug='original'); db.add(org); db.flush()
        community = Community(organization_id=org.id, name='Original community', slug='original'); db.add(community); db.flush()
        membership = Membership(user_id=user.id, community_id=community.id, role=MembershipRole.ADMIN); db.add(membership); db.flush()
        membership_id = membership.id; db.commit()
    payload = grant(client, monkeypatch)
    assert client.post('/api/v1/auth/google/complete', json=payload).status_code == 409
    assert client.post('/api/v1/auth/google/complete', json={**payload, 'password': 'wrong'}).status_code == 401
    response = client.post('/api/v1/auth/google/complete', json={**payload, 'password': 'initial-password-123'})
    assert response.status_code == 200, response.text
    assert response.json()['user']['id'] == original['user']['id']
    assert response.json()['user']['role'] == 'participant'
    assert client.post('/api/v1/auth/login', json={'email': 'member@example.com', 'password': 'initial-password-123'}).status_code == 200
    changed = grant(client, monkeypatch, email='changed@example.com')
    assert client.post('/api/v1/auth/google/complete', json=changed).json()['user']['id'] == original['user']['id']
    conflict = grant(client, monkeypatch, subject='different-subject')
    assert client.post('/api/v1/auth/google/complete', json=conflict).status_code == 409
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1
        assert db.scalar(select(User.email)) == 'member@example.com'
        assert db.get(Membership, membership_id).role == MembershipRole.ADMIN


def test_external_identity_database_uniqueness(env, monkeypatch):
    from sqlalchemy.exc import IntegrityError

    client, engine, _ = env
    assert client.post('/api/v1/auth/google/complete', json=grant(client, monkeypatch)).status_code == 200
    with Session(engine) as db:
        identity = db.scalar(select(ExternalIdentity))
        db.add(ExternalIdentity(user_id=identity.user_id, provider='google', provider_subject='another-subject', provider_email='another@example.com'))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        other = User(email='other@example.com', password_hash=None); db.add(other); db.flush()
        db.add(ExternalIdentity(user_id=other.id, provider='google', provider_subject=identity.provider_subject, provider_email='other@example.com'))
        with pytest.raises(IntegrityError):
            db.commit()


def test_google_suspension_and_restoration(env, monkeypatch):
    client, engine, _ = env
    assert client.post('/api/v1/auth/google/complete', json=grant(client, monkeypatch)).status_code == 200
    with Session(engine) as db:
        user = db.scalar(select(User)); user.is_active = False; db.commit()
    response = client.post('/api/v1/auth/google/complete', json=grant(client, monkeypatch))
    assert response.status_code == 403 and 'suspended' in response.text
    with Session(engine) as db:
        user = db.scalar(select(User)); user.is_active = True; db.commit()
    assert client.post('/api/v1/auth/google/complete', json=grant(client, monkeypatch)).status_code == 200


def test_state_cookie_expiry_cancellation_and_grant_expiry(env, monkeypatch):
    client, engine, _ = env
    response = client.get('/api/v1/auth/google/callback?state=' + 'a' * 64, follow_redirects=False)
    assert response.headers['location'].endswith('error=invalid_state')
    start = client.get('/api/v1/auth/google/start', params={'handoff_challenge': google_identity.challenge('a' * 64)}, follow_redirects=False)
    state = parse_qs(urlsplit(start.headers['location']).query)['state'][0]
    cancelled = client.get('/api/v1/auth/google/callback', params={'state': state, 'error': 'access_denied'}, follow_redirects=False)
    assert cancelled.headers['location'].endswith('error=cancelled')
    assert client.get('/api/v1/auth/google/callback', params={'state': state, 'code': 'replay'}, follow_redirects=False).headers['location'].endswith('error=invalid_state')
    payload = grant(client, monkeypatch)
    with Session(engine) as db:
        flow = db.scalar(select(GoogleAuthFlow).where(GoogleAuthFlow.handoff_hash == hash_token(payload['grant'])))
        flow.expires_at = datetime.now(UTC) - timedelta(seconds=1); db.commit()
    assert client.post('/api/v1/auth/google/complete', json=payload).status_code == 400


def test_reset_generic_cooldown_sessions_and_single_use(env):
    client, _engine, sender = env
    original = register(client)
    verification = sender.messages[-1].token
    first = client.post('/api/v1/auth/password-reset/request', json={'email': 'member@example.com'})
    token = sender.messages[-1].token
    assert '/reset-password#token=' + token in sender.messages[-1].body
    assert '/verify-email' not in sender.messages[-1].body
    assert first.status_code == 202
    count = len(sender.messages)
    assert client.post('/api/v1/auth/password-reset/request', json={'email': 'member@example.com'}).json() == first.json()
    assert client.post('/api/v1/auth/password-reset/request', json={'email': 'absent@example.com'}).json() == first.json()
    assert len(sender.messages) == count
    response = client.post('/api/v1/auth/password-reset/confirm', json={'token': token, 'new_password': 'replacement-password-123'})
    assert response.status_code == 204
    assert client.post('/api/v1/auth/password-reset/confirm', json={'token': token, 'new_password': 'replacement-password-123'}).status_code == 400
    assert client.post('/api/v1/auth/refresh', json={'refresh_token': original['refresh_token']}).status_code == 401
    assert client.post('/api/v1/auth/verify-email', json={'token': verification}).status_code == 204


def test_reset_delivery_failure_and_secret_validation(env):
    client, _, _ = env
    register(client)
    class FailingSender:
        def send_token(self, *_):
            raise OSError('provider-private-detail')
    client.app.dependency_overrides[get_email_sender] = lambda: FailingSender()
    actual = client.post('/api/v1/auth/password-reset/request', json={'email': 'member@example.com'})
    missing = client.post('/api/v1/auth/password-reset/request', json={'email': 'missing@example.com'})
    assert actual.status_code == missing.status_code == 202 and actual.json() == missing.json()
    secret = 'é' * 40
    response = client.post('/api/v1/auth/password-reset/confirm', json={'token': 'a' * 64, 'new_password': secret})
    assert response.status_code == 422 and secret not in response.text


@pytest.mark.parametrize('changed', [{'email_verified': False}, {'nonce': 'wrong'}, {'azp': 'wrong'}, {'sub': ''}])
def test_google_extra_claim_validation(env, monkeypatch, changed):
    claims = {'sub': 'stable-subject', 'email': 'verified@example.com', 'email_verified': True, 'nonce': 'nonce', **changed}
    monkeypatch.setattr(google_identity.id_token, 'verify_oauth2_token', lambda *args: claims)
    with pytest.raises(ValueError):
        google_identity.verify_identity('opaque-test-token', hash_token('nonce'))


@pytest.mark.parametrize('change', [{}, {'aud': 'wrong-client'}, {'iss': 'https://attacker.example'}, {'exp': 1}, {'tamper': True}])
def test_real_google_library_signature_and_standard_claims(env, monkeypatch, change):
    import json
    import time

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from google.auth.exceptions import GoogleAuthError
    from jose import jwt

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    class CertificateResponse:
        status = 200
        data = json.dumps({'test-key': public}).encode()
    monkeypatch.setattr(google_identity, 'BoundedGoogleRequest', lambda: lambda *args, **kwargs: CertificateResponse())
    payload = {'iss': 'https://accounts.google.com', 'aud': 'test-client', 'iat': int(time.time()) - 5,
               'exp': int(time.time()) + 600, 'sub': 'signed-subject', 'nonce': 'nonce',
               'email': 'signed@example.com', 'email_verified': True, **change}
    encoded = jwt.encode(payload, private, algorithm='RS256', headers={'kid': 'test-key'})
    if change.get('tamper'):
        parts = encoded.split('.'); parts[2] = ('A' if parts[2][0] != 'A' else 'B') + parts[2][1:]; encoded = '.'.join(parts)
    if change:
        with pytest.raises((ValueError, GoogleAuthError)):
            google_identity.verify_identity(encoded, hash_token('nonce'))
    else:
        assert google_identity.verify_identity(encoded, hash_token('nonce'))['sub'] == 'signed-subject'


def test_reset_expiry_sibling_tokens_and_suspension(env):
    from src.models.auth import AuthToken, AuthTokenPurpose

    client, engine, sender = env
    register(client)
    client.post('/api/v1/auth/password-reset/request', json={'email': 'member@example.com'})
    token = sender.messages[-1].token
    with Session(engine) as db:
        user = db.scalar(select(User)); user.is_active = False
        db.add(AuthToken(user_id=user.id, purpose=AuthTokenPurpose.PASSWORD_RESET, token_hash=hash_token('sibling-token'), expires_at=datetime.now(UTC) + timedelta(hours=1)))
        db.add(AuthToken(user_id=user.id, purpose=AuthTokenPurpose.PASSWORD_RESET, token_hash=hash_token('expired-token' * 4), expires_at=datetime.now(UTC) - timedelta(hours=1)))
        db.commit()
    assert client.post('/api/v1/auth/password-reset/confirm', json={'token': 'expired-token' * 4, 'new_password': 'replacement-password-123'}).status_code == 400
    count = len(sender.messages)
    assert client.post('/api/v1/auth/password-reset/request', json={'email': 'member@example.com'}).status_code == 202
    assert len(sender.messages) == count
    assert client.post('/api/v1/auth/password-reset/confirm', json={'token': token, 'new_password': 'replacement-password-123'}).status_code == 204
    with Session(engine) as db:
        assert db.scalar(select(User)).is_active is False
        assert all(t.consumed_at is not None for t in db.scalars(select(AuthToken).where(AuthToken.purpose == AuthTokenPurpose.PASSWORD_RESET)))
    assert client.post('/api/v1/auth/login', json={'email': 'member@example.com', 'password': 'replacement-password-123'}).status_code == 403


def test_link_brute_force_is_bounded(env, monkeypatch):
    client, _, _ = env
    register(client)
    payload = grant(client, monkeypatch)
    for _ in range(5):
        assert client.post('/api/v1/auth/google/complete', json={**payload, 'password': 'wrong'}).status_code == 401
    assert client.post('/api/v1/auth/google/complete', json={**payload, 'password': 'initial-password-123'}).status_code == 400


def test_auth_rate_limit_and_log_redaction(env, monkeypatch):
    import logging

    from src.logging_config import SensitiveDataFilter

    client, _, _ = env
    monkeypatch.setattr('src.security_middleware.auth_rate_limiter', RateLimiter(limit=1))
    assert client.post('/api/v1/auth/password-reset/request', json={'email': 'missing@example.com'}).status_code == 202
    assert client.post('/api/v1/auth/password-reset/request', json={'email': 'missing@example.com'}).status_code == 429
    record = logging.LogRecord('uvicorn.access', logging.INFO, '', 1, '%s', ('/api/v1/auth/google/callback?code=private-code&state=private-state',), None)
    SensitiveDataFilter().filter(record)
    assert 'private-code' not in record.getMessage() and 'private-state' not in record.getMessage()
