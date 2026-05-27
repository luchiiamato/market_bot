"""Pytest configuration: tmp DB path + global yfinance mock.

We have to set ``MARKET_BOT_DB_PATH`` **before** any of the production modules
that read it at import time get loaded. To keep that simple, we do it here at
module top-level (pytest imports conftest.py very early).
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Path bootstrap — mirror what services/api/app.py does so imports resolve.
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parents[1]
for _src in (
    _ROOT / "packages" / "engine" / "src",
    _ROOT / "packages" / "identity" / "src",
    _ROOT / "packages" / "portfolio" / "src",
    _ROOT / "packages" / "reference_data" / "src",
    _ROOT / "services",
):
    if str(_src) not in sys.path:
        sys.path.insert(0, str(_src))


# ---------------------------------------------------------------------------
# Tmp DB path — session-wide so every test sees the same isolated DB file.
# Setting the env var here (at import time) guarantees that any module that
# reads MARKET_BOT_DB_PATH lazily inside ``database_path()`` will pick it up.
# ---------------------------------------------------------------------------
_TMP_DB_DIR = tempfile.mkdtemp(prefix="market_bot_tests_")
_TMP_DB_PATH = Path(_TMP_DB_DIR) / "test.db"
os.environ["MARKET_BOT_DB_PATH"] = str(_TMP_DB_PATH)


# ---------------------------------------------------------------------------
# Global yfinance mock. We install a fake module into sys.modules so that any
# ``import yfinance as yf`` inside production code resolves to a harmless
# stub that never touches the network. Individual tests can still override
# its attributes via monkeypatch.
# ---------------------------------------------------------------------------
def _install_yfinance_stub() -> ModuleType:
    stub = ModuleType("yfinance")

    def _download(*_args, **_kwargs):  # pragma: no cover - default branch
        import pandas as pd

        return pd.DataFrame()

    class _Ticker:  # pragma: no cover - default branch
        def __init__(self, *_args, **_kwargs):
            self.news: list[dict] = []
            self.calendar = None
            self.info: dict = {}

        def history(self, *_args, **_kwargs):
            import pandas as pd

            return pd.DataFrame()

    stub.download = _download  # type: ignore[attr-defined]
    stub.Ticker = _Ticker  # type: ignore[attr-defined]
    sys.modules["yfinance"] = stub
    return stub


_install_yfinance_stub()


@pytest.fixture(autouse=True)
def _reset_db(tmp_path, monkeypatch):
    """Per-test fresh DB file. Ensures isolation between tests."""
    db_file = tmp_path / "market_bot.db"
    monkeypatch.setenv("MARKET_BOT_DB_PATH", str(db_file))
    yield db_file


@pytest.fixture()
def fake_yfinance(monkeypatch):
    """Hand a fresh MagicMock-based yfinance module to the test.

    Use ``fake_yfinance.Ticker.return_value.news = [...]`` to seed news,
    or ``fake_yfinance.download.return_value = some_df``.
    """
    stub = ModuleType("yfinance")
    stub.download = MagicMock(name="yf.download")
    stub.Ticker = MagicMock(name="yf.Ticker")
    monkeypatch.setitem(sys.modules, "yfinance", stub)
    return stub


@pytest.fixture()
def api_client(monkeypatch):
    """FastAPI TestClient bound to a freshly imported app.

    We force a reimport so the IdentityService instantiated at module load
    picks up the per-test ``MARKET_BOT_DB_PATH``. Without this the schema
    would be created against a stale path.
    """
    from fastapi.testclient import TestClient

    # Force reimport so module-level singletons rebind to the new DB path.
    for mod_name in list(sys.modules):
        if mod_name.startswith(("services", "api", "market_identity",
                                  "market_portfolio", "market_reference",
                                  "market_bot")):
            sys.modules.pop(mod_name, None)

    from services.api.app import app  # type: ignore[import-not-found]

    with TestClient(app) as client:
        yield client


@pytest.fixture()
def auth_headers(api_client):
    """Register a user and return Authorization headers for it."""
    payload = {
        "username": "testuser",
        "password": "secret123",
        "display_name": "Test User",
    }
    response = api_client.post("/auth/register", json=payload)
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
