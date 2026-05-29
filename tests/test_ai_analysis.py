from __future__ import annotations

from datetime import date, datetime

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
from market_reference import EarningsEvent, NewsItem
from services.api.gemini_analysis_client import AiAnalysisCitation, AiAnalysisResult
from services.api.schemas import MarketOverviewResponse, MarketPulseItemResponse


def _sample_analysis(ticker: str = "AAPL") -> TickerAnalysis:
    return TickerAnalysis(
        ticker=ticker,
        horizon=Horizon.SHORT,
        generated_at=datetime.utcnow(),
        indicators=IndicatorSnapshot(
            price=195.25,
            rsi=58.0,
            macd=1.2,
            macd_signal=0.9,
            adx=24.0,
            atr=3.5,
        ),
        deterministic=DeterministicSignal(
            direction=Direction.LONG,
            score=74.0,
            regime="uptrend",
            setup_name="breakout",
            invalidation="Pierde 190.",
            reasons=["RSI arriba de 50.", "Precio sobre SMA50."],
        ),
        probabilistic=ProbabilisticSignal(
            confidence=0.72,
            probability_up=0.66,
            scenarios=[
                ScenarioProbability(label="bull", probability=0.55, thesis="Bull case."),
                ScenarioProbability(label="base", probability=0.25, thesis="Base case."),
                ScenarioProbability(label="bear", probability=0.20, thesis="Bear case."),
            ],
            dominant_features=["Momentum positivo"],
            warnings=["Evento earnings en menos de 30 días."],
        ),
        actions=[
            ActionSuggestion(
                action=ActionType.GO_LONG,
                conviction=0.72,
                rationale="La estructura acompaña.",
            )
        ],
        catalysts=[],
        guardrails=["Volatilidad moderada."],
    )


def _sample_market_overview(ticker: str = "AAPL") -> MarketOverviewResponse:
    return MarketOverviewResponse(
        generated_at=datetime.utcnow(),
        ticker=ticker,
        horizon="short",
        regime="risk_on",
        breadth="amplio",
        summary="Tape constructivo.",
        warnings=[],
        instruments=[
            MarketPulseItemResponse(
                symbol="SPY",
                label="S&P 500",
                category="indices",
                price=520.0,
                day_change_pct=0.01,
                relative_to_sma20_pct=0.02,
                relative_to_sma50_pct=0.03,
                tone="constructivo",
                note="Índice firme.",
            )
        ],
    )


def _configure_ai_context_stubs(monkeypatch, app_module):
    monkeypatch.setattr(app_module.service, "analyze_ticker", lambda ticker, horizon: _sample_analysis(ticker))
    monkeypatch.setattr(app_module, "_build_market_overview", lambda ticker, horizon: _sample_market_overview(ticker or "AAPL"))
    monkeypatch.setattr(
        app_module,
        "fetch_news",
        lambda ticker: [
            NewsItem(
                ticker=ticker,
                title="Nuevo contrato de infraestructura",
                url="https://example.com/news",
                source="Reuters",
                summary="Catalyst externo.",
                sentiment=0.42,
                impact_category="contract",
                confidence=0.9,
                published_at="2026-05-29T10:00:00Z",
                fetched_at="2026-05-29T10:00:01Z",
            )
        ],
    )
    monkeypatch.setattr(
        app_module,
        "upcoming_earnings",
        lambda tickers, days_ahead=180: [
            EarningsEvent(
                ticker=tickers[0],
                report_date=date(2026, 6, 12),
                report_time="AMC",
                eps_estimate=1.23,
                eps_actual=None,
                revenue_estimate=100.0,
                revenue_actual=None,
            )
        ],
    )
    monkeypatch.setattr(
        app_module,
        "fetch_earnings_history",
        lambda ticker, limit=8: [
            {
                "fiscal_quarter": "Q1 FY27",
                "report_date": date(2026, 4, 30),
                "eps_estimate": 1.2,
                "eps_actual": 1.3,
                "surprise_pct": 0.08,
                "beat": True,
                "next_day_return_pct": 0.03,
                "next_day_close_date": date(2026, 5, 1),
            }
        ],
    )


def test_ai_analysis_requires_gemini_configuration(api_client, monkeypatch):
    import services.api.app as app_module

    monkeypatch.setattr(app_module.gemini_analysis_client, "is_configured", lambda: False)

    response = api_client.post("/analyze/ai", json={"ticker": "AAPL", "horizon": "short"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Gemini no está configurado."


def test_ai_analysis_endpoint_returns_citations_for_guest(api_client, monkeypatch):
    import services.api.app as app_module

    _configure_ai_context_stubs(monkeypatch, app_module)
    captured: dict[str, str] = {}
    monkeypatch.setattr(app_module.gemini_analysis_client, "is_configured", lambda: True)

    def fake_analyze(*, system_prompt, user_prompt, model=None):
        captured["system_prompt"] = system_prompt
        captured["user_prompt"] = user_prompt
        return AiAnalysisResult(
            provider="gemini",
            # model="gemini-2.5-pro",
            model="gemini-3.5-flash",
            content="## Veredicto AI\n- Setup firme.",
            citations=[
                AiAnalysisCitation(
                    title="Reuters contrato",
                    url="https://example.com/news",
                    source="Reuters",
                    published_at="2026-05-29T10:00:00Z",
                )
            ],
            latency_ms=220,
        )

    monkeypatch.setattr(app_module.gemini_analysis_client, "analyze", fake_analyze)

    response = api_client.post("/analyze/ai", json={"ticker": "AAPL", "horizon": "short"})

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["provider"] == "gemini"
    # assert payload["model"] == "gemini-2.5-pro"
    assert payload["model"] == "gemini-3.5-flash"

    assert payload["used_profile_context"] is False
    assert payload["citations"][0]["url"] == "https://example.com/news"
    assert '"news_context"' in captured["user_prompt"]
    assert '"market_context"' in captured["user_prompt"]


def test_ai_analysis_includes_profile_context_when_logged_in(api_client, auth_headers, monkeypatch):
    import services.api.app as app_module

    _configure_ai_context_stubs(monkeypatch, app_module)
    captured: dict[str, str] = {}
    monkeypatch.setattr(app_module.gemini_analysis_client, "is_configured", lambda: True)

    def fake_analyze(*, system_prompt, user_prompt, model=None):
        captured["user_prompt"] = user_prompt
        return AiAnalysisResult(
            provider="gemini",
            # model="gemini-2.5-pro",
            model="gemini-3.5-flash",
            content="## Veredicto AI\n- Perfil moderado, exposición baja al ticker.",
            citations=[],
            latency_ms=180,
        )

    monkeypatch.setattr(app_module.gemini_analysis_client, "analyze", fake_analyze)

    response = api_client.post(
        "/analyze/ai",
        headers=auth_headers,
        json={"ticker": "AAPL", "horizon": "short"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["used_profile_context"] is True
    assert '"portfolio_context"' in captured["user_prompt"]
    assert '"profile"' in captured["user_prompt"]
