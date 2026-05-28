"""Decision audit log — persistence + endpoints."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from market_bot.contracts import (
    ActionSuggestion,
    ActionType,
    DeterministicSignal,
    Direction,
    Horizon,
    IndicatorSnapshot,
    ProbabilisticSignal,
    ScenarioProbability,
    TickerAnalysis,
)
from services.api.logging_config import reset_rate_buckets


@pytest.fixture(autouse=True)
def _reset_rate_buckets():
    reset_rate_buckets()
    yield
    reset_rate_buckets()


def _stub_analysis(ticker: str = "AAPL") -> TickerAnalysis:
    return TickerAnalysis(
        ticker=ticker,
        horizon=Horizon.SHORT,
        generated_at=datetime.utcnow(),
        indicators=IndicatorSnapshot(price=180.0),
        deterministic=DeterministicSignal(
            direction=Direction.LONG,
            score=70.0,
            regime="trend",
            setup_name="continuation",
            invalidation="Below 175.",
            reasons=["MA50 above MA200."],
        ),
        probabilistic=ProbabilisticSignal(
            confidence=0.7,
            probability_up=0.65,
            scenarios=[
                ScenarioProbability(label="bull", probability=0.6, thesis="Bull."),
                ScenarioProbability(label="base", probability=0.3, thesis="Base."),
                ScenarioProbability(label="bear", probability=0.1, thesis="Bear."),
            ],
            dominant_features=["trend"],
            warnings=[],
        ),
        actions=[
            ActionSuggestion(
                action=ActionType.BUY,
                conviction=0.7,
                rationale="Estructura alcista clara.",
            )
        ],
        catalysts=[],
        guardrails=[],
    )


def test_create_decision_persists_snapshot(api_client, auth_headers, monkeypatch):
    import services.api.app as app_module

    monkeypatch.setattr(
        app_module.service,
        "analyze_ticker",
        lambda ticker, horizon: _stub_analysis(ticker),
    )

    response = api_client.post(
        "/decisions",
        headers=auth_headers,
        json={
            "ticker": "AAPL",
            "horizon": "short",
            "action_taken": "bought",
            "rationale": "Setup limpio post-earnings.",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["ticker"] == "AAPL"
    assert body["action_taken"] == "bought"
    assert body["conviction"] == pytest.approx(0.7)
    assert body["analysis_snapshot"]["ticker"] == "AAPL"
    assert body["analysis_snapshot"]["deterministic"]["direction"] == "long"


def test_list_decisions_returns_only_current_user(api_client, auth_headers, monkeypatch):
    import services.api.app as app_module

    monkeypatch.setattr(
        app_module.service,
        "analyze_ticker",
        lambda ticker, horizon: _stub_analysis(ticker),
    )

    api_client.post(
        "/decisions",
        headers=auth_headers,
        json={"ticker": "AAPL", "horizon": "short", "action_taken": "bought"},
    )
    api_client.post(
        "/decisions",
        headers=auth_headers,
        json={"ticker": "NVDA", "horizon": "long", "action_taken": "hold"},
    )

    listed = api_client.get("/decisions", headers=auth_headers)
    assert listed.status_code == 200
    tickers = sorted(item["ticker"] for item in listed.json())
    assert tickers == ["AAPL", "NVDA"]


def test_list_decisions_filters_by_ticker(api_client, auth_headers, monkeypatch):
    import services.api.app as app_module

    monkeypatch.setattr(
        app_module.service,
        "analyze_ticker",
        lambda ticker, horizon: _stub_analysis(ticker),
    )

    for ticker in ("AAPL", "NVDA", "MELI"):
        api_client.post(
            "/decisions",
            headers=auth_headers,
            json={"ticker": ticker, "horizon": "short", "action_taken": "bought"},
        )

    response = api_client.get("/decisions?ticker=NVDA", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["ticker"] == "NVDA"


def test_create_decision_requires_auth(api_client):
    response = api_client.post(
        "/decisions",
        json={"ticker": "AAPL", "horizon": "short", "action_taken": "bought"},
    )
    assert response.status_code == 401
