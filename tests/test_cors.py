"""CORS allowlist and preflight behavior."""
from fastapi.testclient import TestClient

from src.config import Settings
from src.main import create_app

FRONTEND = "https://tickvendor-1.onrender.com"


def test_settings_accepts_render_json_and_comma_cors_values():
    assert Settings(cors_origins=f'["{FRONTEND}"]').cors_origins == [FRONTEND]
    assert Settings(cors_origins=FRONTEND).cors_origins == [FRONTEND]


def test_allowed_origin_preflight_and_register_response_are_cors_enabled(monkeypatch):
    monkeypatch.setattr("src.main.settings.cors_origins", [FRONTEND])
    client = TestClient(create_app())
    preflight = client.options(
        "/api/v1/auth/register",
        headers={"Origin": FRONTEND, "Access-Control-Request-Method": "POST",
                 "Access-Control-Request-Headers": "content-type"},
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == FRONTEND
    response = client.post(
        "/api/v1/auth/register", headers={"Origin": FRONTEND}, json={"invalid": True}
    )
    assert response.status_code == 422
    assert response.headers["access-control-allow-origin"] == FRONTEND


def test_foreign_origin_is_not_allowed(monkeypatch):
    monkeypatch.setattr("src.main.settings.cors_origins", [FRONTEND])
    client = TestClient(create_app())
    response = client.options(
        "/api/v1/auth/register",
        headers={"Origin": "https://foreign.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in response.headers