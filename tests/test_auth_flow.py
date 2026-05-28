"""End-to-end auth flow: register → /profile → logout → 401."""

from __future__ import annotations

import sys

import pytest

from services.api.logging_config import reset_rate_buckets


@pytest.fixture(autouse=True)
def _reset_rate_buckets():
    """Stop rate-limit state from one test poisoning another."""
    reset_rate_buckets()
    yield
    reset_rate_buckets()


def test_register_then_login_then_profile_roundtrip(api_client):
    register = api_client.post(
        "/auth/register",
        json={"username": "alice", "password": "secret123", "display_name": "Alice"},
    )
    assert register.status_code == 201, register.text
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    profile = api_client.get("/profile", headers=headers)
    assert profile.status_code == 200
    body = profile.json()
    assert body["username"] == "alice"
    assert body["display_name"] == "Alice"
    assert body["investor_profile"] == "moderate"  # default


def test_login_with_wrong_password_returns_401(api_client):
    api_client.post(
        "/auth/register",
        json={"username": "bob", "password": "rightpass123"},
    )
    login = api_client.post(
        "/auth/login",
        json={"username": "bob", "password": "wrongpass"},
    )
    assert login.status_code == 401


def test_logout_invalidates_token(api_client):
    register = api_client.post(
        "/auth/register",
        json={"username": "carol", "password": "secret123"},
    )
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert api_client.get("/profile", headers=headers).status_code == 200
    logout = api_client.post("/auth/logout", headers=headers)
    assert logout.status_code == 204
    # Same token now rejected.
    assert api_client.get("/profile", headers=headers).status_code == 401


def test_login_rate_limited_after_too_many_attempts(api_client):
    api_client.post(
        "/auth/register",
        json={"username": "dave", "password": "secret123"},
    )
    # 5 failed attempts within the window — 6th should be 429.
    for _ in range(5):
        response = api_client.post(
            "/auth/login",
            json={"username": "dave", "password": "wrongpw1"},
        )
        assert response.status_code == 401
    blocked = api_client.post(
        "/auth/login",
        json={"username": "dave", "password": "wrongpw1"},
    )
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_request_id_header_present(api_client):
    response = api_client.get("/health")
    assert response.status_code == 200
    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) >= 16


def test_root_redirects_to_frontend_when_entrypoint_exists(api_client):
    response = api_client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/app/"


def test_root_redirects_to_docs_when_frontend_is_not_packaged(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("MARKET_BOT_DB_PATH", str(tmp_path / "market_bot.db"))

    for mod_name in list(sys.modules):
        if mod_name.startswith(("services", "api", "market_identity", "market_portfolio", "market_reference", "market_bot")):
            sys.modules.pop(mod_name, None)

    import services.api.app as app_module  # type: ignore[import-not-found]

    monkeypatch.setattr(app_module, "_frontend_entrypoint_exists", lambda: False)

    with TestClient(app_module.app) as client:
        response = client.get("/", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/docs"


def test_cors_allows_vercel_preview_origins_via_regex(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("MARKET_BOT_DB_PATH", str(tmp_path / "market_bot.db"))
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://market-bot.vercel.app")
    monkeypatch.setenv("CORS_ALLOW_ORIGIN_REGEX", r"^https://market-bot(?:-[a-z0-9-]+)?\.vercel\.app$")

    for mod_name in list(sys.modules):
        if mod_name.startswith(("services", "api", "market_identity", "market_portfolio", "market_reference", "market_bot")):
            sys.modules.pop(mod_name, None)

    from services.api.app import app  # type: ignore[import-not-found]

    with TestClient(app) as client:
        response = client.options(
            "/health",
            headers={
                "Origin": "https://market-bot-git-main-luciano.vercel.app",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200, response.text
    assert response.headers["access-control-allow-origin"] == "https://market-bot-git-main-luciano.vercel.app"
