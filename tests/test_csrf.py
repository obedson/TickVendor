"""CSRF middleware tests for cookie-authenticated unsafe requests."""
from fastapi.testclient import TestClient

from src.main import create_app


def test_cookie_mutation_requires_allowed_origin_and_double_submit_token():
    client = TestClient(create_app())
    path = "/api/v1/auth/logout"
    cookies = {"access_token": "cookie-session", "csrf_token": "known-token"}

    missing = client.post(path, cookies=cookies, headers={"Origin": "http://localhost:5173"})
    assert missing.status_code == 403

    outsider = client.post(
        path,
        cookies=cookies,
        headers={"Origin": "https://attacker.example", "X-CSRF-Token": "known-token"},
    )
    assert outsider.status_code == 403

    mismatch = client.post(
        path,
        cookies=cookies,
        headers={"Origin": "http://localhost:5173", "X-CSRF-Token": "wrong-token"},
    )
    assert mismatch.status_code == 403

    accepted = client.post(
        path,
        cookies=cookies,
        headers={"Origin": "http://localhost:5173", "X-CSRF-Token": "known-token"},
    )
    assert accepted.status_code == 422  # CSRF passed; request-body validation now applies.


def test_bearer_api_request_does_not_require_csrf_token():
    response = TestClient(create_app()).post(
        "/api/v1/auth/logout",
        headers={"Authorization": "Bearer explicitly-supplied-token"},
    )
    assert response.status_code == 422
