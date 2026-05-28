from __future__ import annotations

import importlib
import io
import zipfile
from datetime import date, datetime
from types import SimpleNamespace

from market_bot.contracts import (
    ActionSuggestion,
    ActionType,
    Catalyst,
    CatalystStatus,
    DeterministicSignal,
    Direction,
    Horizon,
    IndicatorSnapshot,
    ProbabilisticSignal,
    ScenarioProbability,
    TickerAnalysis,
)
from market_bot.service import _apply_rumor_policy
from market_portfolio.models import BenchmarkComparison, PositionRecord, PositionValuation
from market_portfolio.service import PortfolioService
from market_reference import EarningsEvent, NewsItem


def _sample_analysis(ticker: str = "AAPL") -> TickerAnalysis:
    return TickerAnalysis(
        ticker=ticker,
        horizon=Horizon.SHORT,
        generated_at=datetime.utcnow(),
        indicators=IndicatorSnapshot(price=195.25, atr=2.5),
        deterministic=DeterministicSignal(
            direction=Direction.LONG,
            score=71.0,
            regime="trend",
            setup_name="trend_continuation",
            invalidation="Perder 190.",
            reasons=["RSI arriba de 50."],
        ),
        probabilistic=ProbabilisticSignal(
            confidence=0.74,
            probability_up=0.66,
            scenarios=[
                ScenarioProbability(label="bull", probability=0.54, thesis="Bull case."),
                ScenarioProbability(label="base", probability=0.24, thesis="Base case."),
                ScenarioProbability(label="bear", probability=0.22, thesis="Bear case."),
            ],
            dominant_features=["RSI apoya al alza"],
            warnings=[],
        ),
        actions=[
            ActionSuggestion(
                action=ActionType.GO_LONG,
                conviction=0.74,
                rationale="La lectura tactica favorece continuidad alcista.",
            )
        ],
        catalysts=[],
        guardrails=[],
    )


def _minimal_balanz_xlsx() -> bytes:
    workbook_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
      xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
      <sheets>
        <sheet name="resultados_por_lotes_finales" sheetId="1" r:id="rId1"/>
      </sheets>
    </workbook>"""
    rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
      <Relationship Id="rId1"
        Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
        Target="worksheets/sheet1.xml"/>
    </Relationships>"""
    sheet_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
      <sheetData>
        <row r="1">
          <c r="A1" t="inlineStr"><is><t>Cantidad</t></is></c>
          <c r="B1" t="inlineStr"><is><t>Descripcion</t></is></c>
          <c r="C1" t="inlineStr"><is><t>Fecha</t></is></c>
          <c r="D1" t="inlineStr"><is><t>Fecha Lote</t></is></c>
          <c r="E1" t="inlineStr"><is><t>Gastos</t></is></c>
          <c r="F1" t="inlineStr"><is><t>Moneda</t></is></c>
          <c r="G1" t="inlineStr"><is><t>Operacion</t></is></c>
          <c r="H1" t="inlineStr"><is><t>Precio Compra</t></is></c>
          <c r="I1" t="inlineStr"><is><t>Ticker</t></is></c>
          <c r="J1" t="inlineStr"><is><t>Tipo</t></is></c>
        </row>
        <row r="2">
          <c r="A2" t="n"><v>40</v></c>
          <c r="B2" t="inlineStr"><is><t>CEDEAR APPLE INC.</t></is></c>
          <c r="C2" t="inlineStr"><is><t>2026-01-28</t></is></c>
          <c r="D2" t="inlineStr"><is><t>2026-05-27</t></is></c>
          <c r="E2" t="n"><v>4227.5</v></c>
          <c r="F2" t="inlineStr"><is><t>Pesos</t></is></c>
          <c r="G2" t="inlineStr"><is><t>Boleto</t></is></c>
          <c r="H2" t="n"><v>19410</v></c>
          <c r="I2" t="inlineStr"><is><t>AAPL</t></is></c>
          <c r="J2" t="inlineStr"><is><t>Cedears</t></is></c>
        </row>
        <row r="3">
          <c r="A3" t="n"><v>1760</v></c>
          <c r="B3" t="inlineStr"><is><t>BONO REP. ARGENTINA USD STEP UP 2030</t></is></c>
          <c r="C3" t="inlineStr"><is><t>2026-01-28</t></is></c>
          <c r="D3" t="inlineStr"><is><t>2026-05-27</t></is></c>
          <c r="E3" t="n"><v>6337.34</v></c>
          <c r="F3" t="inlineStr"><is><t>Pesos</t></is></c>
          <c r="G3" t="inlineStr"><is><t>Boleto</t></is></c>
          <c r="H3" t="n"><v>894.6</v></c>
          <c r="I3" t="inlineStr"><is><t>AL30</t></is></c>
          <c r="J3" t="inlineStr"><is><t>Bonos - Dólar</t></is></c>
        </row>
      </sheetData>
    </worksheet>"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", rels_xml)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return buffer.getvalue()


def test_rankings_endpoint_accepts_three_tuple_and_exposes_why_for_you(
    api_client,
    auth_headers,
    monkeypatch,
):
    import services.api.app as app_module

    captured: dict[str, object] = {}

    def fake_rank_universe(
        horizon, tickers=None, limit=10, cedear_only=True, profile=None, mode="default"
    ):
        captured["profile"] = profile
        captured["mode"] = mode
        return [(_sample_analysis(), 88.4, ["Setup alcista alineado a tu perfil."])]

    monkeypatch.setattr(app_module.service, "rank_universe", fake_rank_universe)

    response = api_client.get("/rankings", headers=auth_headers)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload[0]["why_for_you"] == ["Setup alcista alineado a tu perfil."]
    assert captured["profile"] is not None


def test_public_news_endpoint_allows_anonymous(api_client, monkeypatch):
    import services.api.app as app_module

    monkeypatch.setattr(
        app_module,
        "fetch_news",
        lambda ticker: [
            NewsItem(
                ticker=ticker,
                title="Contract win",
                url="https://example.com/story",
                source="Reuters",
                summary="Sample",
                sentiment=0.3,
                impact_category="guidance",
                confidence=0.8,
                published_at="2026-01-20T00:00:00Z",
                fetched_at="2026-01-20T00:00:01Z",
            )
        ],
    )

    response = api_client.get("/news/AAPL")

    assert response.status_code == 200, response.text
    assert response.json()[0]["ticker"] == "AAPL"


def test_public_ticker_earnings_endpoint_allows_anonymous(api_client, monkeypatch):
    import services.api.app as app_module

    monkeypatch.setattr(
        app_module,
        "upcoming_earnings",
        lambda tickers, days_ahead=180: [
            EarningsEvent(
                ticker=tickers[0],
                report_date=date(2026, 2, 12),
                report_time="AMC",
                eps_estimate=1.23,
                eps_actual=None,
                revenue_estimate=None,
                revenue_actual=None,
            )
        ],
    )

    response = api_client.get("/earnings/AAPL")

    assert response.status_code == 200, response.text
    assert response.json()[0]["ticker"] == "AAPL"


def test_public_market_overview_endpoint_allows_anonymous(api_client, monkeypatch):
    import services.api.app as app_module

    monkeypatch.setattr(
        app_module,
        "_build_market_overview",
        lambda ticker, horizon: {
            "generated_at": datetime.utcnow(),
            "ticker": ticker,
            "horizon": horizon.value,
            "regime": "risk_on",
            "breadth": "amplio",
            "summary": "Tape constructivo.",
            "warnings": [],
            "instruments": [
                {
                    "symbol": "SPY",
                    "label": "S&P 500",
                    "category": "indices",
                    "price": 500.0,
                    "day_change_pct": 0.01,
                    "relative_to_sma20_pct": 0.02,
                    "relative_to_sma50_pct": 0.03,
                    "tone": "bull",
                    "note": "Arriba de medias."
                }
            ],
        },
    )

    response = api_client.get("/market/overview?ticker=AAPL&horizon=short")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ticker"] == "AAPL"
    assert payload["regime"] == "risk_on"
    assert payload["instruments"][0]["symbol"] == "SPY"


def test_logged_in_balanz_import_endpoint_imports_supported_rows_and_skips_unsupported(
    api_client,
    auth_headers,
    monkeypatch,
):
    import services.api.app as app_module

    exchange = SimpleNamespace(official=1000.0, mep=1200.0, ccl=1500.0)
    snapshot = SimpleNamespace(
        purchase_exchange=exchange,
        current_exchange=exchange,
        inflation_factor=1.0,
        fixed_term_factor=1.0,
    )
    monkeypatch.setattr(
        app_module.portfolio_service.benchmark_service,
        "get_current_exchange_rates",
        lambda: exchange,
    )
    monkeypatch.setattr(
        app_module.portfolio_service.benchmark_service,
        "build_period_snapshot",
        lambda start_date, end_date: snapshot,
    )
    monkeypatch.setattr(
        app_module.portfolio_service,
        "_latest_close",
        lambda symbol: (10000.0, date.today()) if str(symbol).endswith(".BA") else (100.0, date.today()),
    )

    response = api_client.post(
        "/portfolio/import/balanz",
        headers={
            **auth_headers,
            "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        },
        content=_minimal_balanz_xlsx(),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["source_sheet"] == "resultados_por_lotes_finales"
    assert payload["imported_count"] == 1
    assert payload["skipped_count"] == 1
    assert payload["positions_count_after"] == 1
    assert payload["imported_symbols"] == ["AAPL"]
    assert "Tipo no soportado" in payload["skipped_rows"][0]["reason"]


def test_create_position_rejects_htmlish_symbol(api_client, auth_headers):
    response = api_client.post(
        "/portfolio/positions",
        headers=auth_headers,
        json={
            "instrument_type": "stock",
            "symbol": "<svg/onload=1>",
            "quantity": 1,
            "purchase_date": "2026-01-01",
            "purchase_price": 10,
            "purchase_currency": "USD",
            "notes": "demo",
        },
    )

    assert response.status_code == 422


def test_rumor_policy_keeps_probability_up_consistent_with_capped_scenarios():
    signal = ProbabilisticSignal(
        confidence=0.8,
        probability_up=0.9,
        scenarios=[
            ScenarioProbability(label="bull", probability=0.8, thesis="Bull."),
            ScenarioProbability(label="base", probability=0.1, thesis="Base."),
            ScenarioProbability(label="bear", probability=0.1, thesis="Bear."),
        ],
        dominant_features=[],
        warnings=[],
    )

    adjusted = _apply_rumor_policy(
        signal,
        [Catalyst(name="Leak", category="news", impact="high", status=CatalystStatus.RUMORED)],
    )

    scenario_probabilities = {scenario.label: scenario.probability for scenario in adjusted.scenarios}
    expected_probability_up = round(
        scenario_probabilities["bull"] + (scenario_probabilities["base"] * 0.5),
        2,
    )

    assert adjusted.probability_up == expected_probability_up
    assert adjusted.probability_up != signal.probability_up
    assert any("rumor-policy" in warning for warning in adjusted.warnings)


def test_analyze_ticker_skips_context_pipeline_when_include_context_is_false(monkeypatch):
    service_module = importlib.import_module("market_bot.service")

    class DummyAdapter:
        def get_price_history(self, ticker, horizon):
            return SimpleNamespace(frame=SimpleNamespace())

        def get_instrument_context(self, ticker):
            raise AssertionError("Context should not be fetched for ranking fast-path.")

    monkeypatch.setattr(service_module, "compute_indicators", lambda frame: frame)
    monkeypatch.setattr(
        service_module,
        "build_indicator_snapshot",
        lambda frame: IndicatorSnapshot(price=100.0),
    )
    monkeypatch.setattr(
        service_module,
        "generate_deterministic_signal",
        lambda frame, horizon: DeterministicSignal(
            direction=Direction.NEUTRAL,
            score=50.0,
            regime="range",
            setup_name="wait",
            invalidation="N/A",
            reasons=[],
        ),
    )
    monkeypatch.setattr(
        service_module,
        "generate_probabilistic_signal",
        lambda frame, indicators, deterministic, horizon: SimpleNamespace(
            signal=ProbabilisticSignal(
                confidence=0.55,
                probability_up=0.5,
                scenarios=[ScenarioProbability(label="base", probability=1.0, thesis="Base.")],
                dominant_features=[],
                warnings=[],
            ),
            validation=None,
        ),
    )

    def fail_context(*args, **kwargs):
        raise AssertionError("Contextual notes should not be built in fast-path ranking.")

    monkeypatch.setattr(service_module, "_build_contextual_notes", fail_context)

    service = service_module.MarketBotService(adapter=DummyAdapter())
    analysis = service.analyze_ticker(
        "AAPL",
        Horizon.SHORT,
        include_context=False,
        include_backtest=False,
    )

    assert analysis.catalysts == []
    assert analysis.guardrails == []


def test_portfolio_valuation_uses_profile_risk_tolerance_for_earnings_guardrail(monkeypatch):
    import market_reference.earnings as earnings_module

    class FakeBenchmarkService:
        def build_period_snapshot(self, start_date, end_date):
            exchange = SimpleNamespace(official=100.0, mep=100.0, ccl=100.0)
            return SimpleNamespace(current_exchange=exchange, purchase_exchange=exchange)

    service = PortfolioService(benchmark_service=FakeBenchmarkService())
    monkeypatch.setattr(service, "_latest_close", lambda symbol: (100.0, date.today()))
    monkeypatch.setattr(service, "_cost_basis", lambda position, snapshot, selected_house: (80.0, 0.8))
    monkeypatch.setattr(
        service,
        "_benchmark_comparisons",
        lambda cost_basis_ars, current_value_ars, snapshot: [
            BenchmarkComparison(
                label="inflation",
                tracked_value_ars=90.0,
                outperformance_ars=10.0,
                outperformance_pct=0.1111,
            )
        ],
    )

    captured: dict[str, str] = {}

    def fake_guardrail(ticker: str, risk_tolerance: str) -> str:
        captured["risk_tolerance"] = risk_tolerance
        return f"{ticker}: earnings pronto."

    monkeypatch.setattr(earnings_module, "earnings_guardrail_for_holding", fake_guardrail)

    valuation = service._build_position_valuation(
        PositionRecord(
            position_id=1,
            user_id=1,
            instrument_type="stock",
            symbol="AAPL",
            underlying_ticker="AAPL",
            byma_symbol=None,
            cedear_ratio=None,
            cedear_ratio_source=None,
            quantity=1,
            purchase_date=date(2026, 1, 10),
            purchase_price=90.0,
            purchase_currency="USD",
            notes="",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
        "mep",
        risk_tolerance="low",
    )

    assert captured["risk_tolerance"] == "low"
    assert any("earnings pronto" in note for note in valuation.notes)


def test_cedear_current_value_usd_uses_ccl_conversion_not_inferred_ratio(monkeypatch):
    """Regression for the 25 ARS/USD bug: when the stored cedear_ratio is wrong
    (or never inferred), the USD value used to balloon because we did
    `(qty / ratio) × underlying_usd`. We now convert via current CCL, so the
    USD figure stays in sync with what the user would actually receive when
    dollarizing the ARS proceeds.
    """

    class FakeBenchmarkService:
        def build_period_snapshot(self, start_date, end_date):
            current = SimpleNamespace(official=900.0, mep=1180.0, ccl=1200.0)
            purchase = SimpleNamespace(official=850.0, mep=1100.0, ccl=1120.0)
            return SimpleNamespace(
                current_exchange=current,
                purchase_exchange=purchase,
                inflation_factor=1.10,
                fixed_term_factor=1.08,
            )

    service = PortfolioService(benchmark_service=FakeBenchmarkService())

    # Local BYMA price 8485 ARS, underlying GOOGL 180 USD. If the stored ratio
    # falls back to 1, the old formula would give 109 × 180 = 19,620 USD.
    # The new formula gives 109 × 8485 / 1200 = 770.93 USD, which is what the
    # user would actually receive selling the CEDEAR at parity.
    def fake_close(symbol):
        if symbol.endswith(".BA"):
            return (8485.0, date.today())
        return (180.0, date.today())

    monkeypatch.setattr(service, "_latest_close", fake_close)

    position = PositionRecord(
        position_id=1,
        user_id=1,
        instrument_type="cedear",
        symbol="GOOGL",
        underlying_ticker="GOOGL",
        byma_symbol="GOOGL.BA",
        cedear_ratio=1.0,  # The bug case: ratio defaulted to 1.
        cedear_ratio_source="fallback_default",
        quantity=109,
        purchase_date=date(2026, 1, 7),
        purchase_price=8485.0,
        purchase_currency="ARS",
        notes="",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    valuation = service._build_position_valuation(position, "ccl", risk_tolerance="medium")

    # ARS value = 109 × 8485 = 924,865
    assert valuation.current_value_ars == 924865.0
    # USD value via CCL = 924,865 / 1200 ≈ 770.72
    assert 760.0 < valuation.current_value_usd < 780.0
    # The old buggy path would have given 19,620 USD — assert we're nowhere near that.
    assert valuation.current_value_usd < 5000.0
    # Implied FX between ARS and USD figures should match the CCL we used.
    implied_fx = valuation.current_value_ars / valuation.current_value_usd
    assert 1190 < implied_fx < 1210


def test_catalyst_boost_lifts_score_for_fresh_earnings():
    """Regression for the "SNOW reported and didn't appear in ranking" complaint.

    A ticker with a fresh REPORTED earnings catalyst should outrank an
    otherwise-identical ticker without one. The boost has to be visible in the
    final score so the top-N cut surfaces the mover."""
    from market_bot.strategies.policy import adjust_rank_for_catalysts

    fresh = _sample_analysis()
    fresh.catalysts = [
        Catalyst(
            name="SNOW Q1 beat expectations",
            category="earnings",
            impact="positive",
            status=CatalystStatus.REPORTED,
            observed_at=datetime.utcnow(),
        )
    ]
    quiet = _sample_analysis()
    quiet.catalysts = []

    fresh_score, fresh_reasons = adjust_rank_for_catalysts(70.0, fresh)
    quiet_score, _ = adjust_rank_for_catalysts(70.0, quiet)

    assert fresh_score > quiet_score
    assert fresh_score / quiet_score >= 1.15
    assert any("fresca" in reason.lower() or "catalyst" in reason.lower() for reason in fresh_reasons)


def test_opportunity_filter_drops_quiet_megacap_keeps_news_driven_name():
    """Opportunities mode should filter out names that have no live catalyst,
    no volume spike, no outsized volatility, no high conviction — i.e. tickers
    drifting sideways. SNOW reporting today qualifies; SPY at 0.5% ATR doesn't.
    """
    from market_bot.strategies.policy import is_opportunity_candidate

    sleepy = _sample_analysis()
    sleepy.catalysts = []
    sleepy.indicators.atr = 0.5
    sleepy.indicators.volume_ratio = 0.9
    sleepy.probabilistic.confidence = 0.5

    mover = _sample_analysis()
    mover.catalysts = [
        Catalyst(
            name="Earnings beat",
            category="earnings",
            impact="positive",
            status=CatalystStatus.CONFIRMED,
        )
    ]

    assert is_opportunity_candidate(mover) is True
    assert is_opportunity_candidate(sleepy) is False


def test_rankings_endpoint_passes_mode_through_to_service(api_client, auth_headers, monkeypatch):
    """The opportunities mode has to actually reach the engine — otherwise the
    UI toggle is cosmetic. Capture the kwarg and assert it round-trips."""
    import services.api.app as app_module

    captured: dict[str, object] = {}

    def fake_rank_universe(
        horizon, tickers=None, limit=10, cedear_only=True, profile=None, mode="default"
    ):
        captured["mode"] = mode
        return [(_sample_analysis(), 95.0, ["Catalyst confirmado."])]

    monkeypatch.setattr(app_module.service, "rank_universe", fake_rank_universe)

    response = api_client.get("/rankings?mode=opportunities", headers=auth_headers)
    assert response.status_code == 200
    assert captured["mode"] == "opportunities"

    response = api_client.get("/rankings", headers=auth_headers)
    assert response.status_code == 200
    assert captured["mode"] == "default"

    # Invalid mode should be rejected by pydantic pattern.
    response = api_client.get("/rankings?mode=nonsense", headers=auth_headers)
    assert response.status_code == 422


def test_balanz_currency_normalizer_handles_accented_dolares():
    """Regression for the Balanz importer dropping rows that listed currency
    as "Dólares" (capital D with accent). The previous .lower() left the accent
    in place, so `"dolar" in "dólares"` returned False and legitimate USD rows
    were rejected as "Moneda no soportada"."""
    from market_portfolio.balanz import _normalize_currency

    assert _normalize_currency("Dólares") == "USD"
    assert _normalize_currency("DÓLARES") == "USD"
    assert _normalize_currency("dolares") == "USD"
    assert _normalize_currency("Dólar Estadounidense") == "USD"
    assert _normalize_currency("USD") == "USD"
    assert _normalize_currency("Pesos") == "ARS"
    assert _normalize_currency("Pesos Argentinos") == "ARS"
    assert _normalize_currency("ARS") == "ARS"


def test_update_position_endpoint_returns_updated_position(api_client, auth_headers, monkeypatch):
    import services.api.app as app_module

    monkeypatch.setattr(
        app_module.portfolio_service,
        "update_position",
        lambda **kwargs: PositionValuation(
            position_id=kwargs["position_id"],
            instrument_type=kwargs["instrument_type"],
            symbol=kwargs["symbol"],
            underlying_ticker=kwargs["underlying_ticker"] or kwargs["symbol"],
            byma_symbol="AAPL.BA",
            cedear_ratio=10.0,
            cedear_ratio_source="user_supplied",
            quantity=kwargs["quantity"],
            purchase_date=kwargs["purchase_date"],
            purchase_price=kwargs["purchase_price"],
            purchase_currency=kwargs["purchase_currency"],
            user_notes=kwargs["notes"],
            current_price=25000.0,
            current_price_currency="ARS",
            quote_as_of=date(2026, 5, 28),
            current_value_ars=50000.0,
            current_value_usd=40.0,
            cost_basis_ars=42000.0,
            cost_basis_usd=33.0,
            pnl_ars=8000.0,
            pnl_usd=7.0,
            return_pct_ars=0.19,
            return_pct_usd=0.21,
            real_return_pct=0.08,
            benchmark_comparisons=[
                BenchmarkComparison(
                    label="inflation",
                    tracked_value_ars=45000.0,
                    outperformance_ars=5000.0,
                    outperformance_pct=0.11,
                )
            ],
            notes=["Earnings en 7 dias."],
        ),
    )

    response = api_client.put(
        "/portfolio/positions/42",
        headers=auth_headers,
        json={
            "instrument_type": "cedear",
            "symbol": "AAPL",
            "quantity": 2,
            "purchase_date": "2026-01-15",
            "purchase_price": 21000,
            "purchase_currency": "ARS",
            "underlying_ticker": "AAPL",
            "cedear_ratio": 10,
            "notes": "Lote corregido",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["position_id"] == 42
    assert payload["user_notes"] == "Lote corregido"
    assert payload["notes"] == ["Earnings en 7 dias."]


def test_news_endpoint_uses_server_side_cache(api_client, monkeypatch):
    import services.api.app as app_module

    calls = {"count": 0}

    def fake_fetch_news(ticker):
        calls["count"] += 1
        return [
            NewsItem(
                ticker=ticker,
                title="Contract win",
                url="https://example.com/story",
                source="Reuters",
                summary="Sample",
                sentiment=0.3,
                impact_category="guidance",
                confidence=0.8,
                published_at="2026-01-20T00:00:00Z",
                fetched_at="2026-01-20T00:00:01Z",
            )
        ]

    monkeypatch.setattr(app_module, "fetch_news", fake_fetch_news)

    first = api_client.get("/news/AAPL")
    second = api_client.get("/news/AAPL")

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert calls["count"] == 1


def test_ticker_earnings_endpoint_uses_server_side_cache(api_client, monkeypatch):
    import services.api.app as app_module

    calls = {"count": 0}

    def fake_upcoming_earnings(tickers, days_ahead=180):
        calls["count"] += 1
        return [
            EarningsEvent(
                ticker=tickers[0],
                report_date=date(2026, 2, 12),
                report_time="AMC",
                eps_estimate=1.23,
                eps_actual=None,
                revenue_estimate=None,
                revenue_actual=None,
            )
        ]

    monkeypatch.setattr(app_module, "upcoming_earnings", fake_upcoming_earnings)

    first = api_client.get("/earnings/AAPL?days_ahead=120")
    second = api_client.get("/earnings/AAPL?days_ahead=120")

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert calls["count"] == 1


def test_public_earnings_history_endpoint_returns_grid_payload(api_client, monkeypatch):
    """The 4x3 surprise grid endpoint must be reachable anonymously (like the
    other earnings reads) and serialise the adapter rows via the response
    schema. We monkeypatch the adapter so the test runs offline — yfinance
    network access is unreliable in CI."""
    import services.api.app as app_module

    def fake_history(ticker, limit=12):
        assert limit == 12
        return [
            {
                "fiscal_quarter": "Q1 FY26",
                "report_date": "2026-02-26",
                "eps_estimate": 0.18,
                "eps_actual": 0.22,
                "surprise_pct": 0.2222,
                "beat": True,
                "next_day_return_pct": 0.084,
                "next_day_close_date": "2026-02-27",
            },
            {
                "fiscal_quarter": "Q4 FY25",
                "report_date": "2025-11-20",
                "eps_estimate": 0.20,
                "eps_actual": 0.15,
                "surprise_pct": -0.25,
                "beat": False,
                "next_day_return_pct": -0.061,
                "next_day_close_date": "2025-11-21",
            },
        ]

    monkeypatch.setattr(app_module, "fetch_earnings_history", fake_history)

    response = api_client.get("/earnings/SNOW/history")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ticker"] == "SNOW"
    assert len(payload["events"]) == 2
    first = payload["events"][0]
    assert first["fiscal_quarter"] == "Q1 FY26"
    assert first["beat"] is True
    assert first["surprise_pct"] == 0.2222
    assert first["next_day_close_date"] == "2026-02-27"
    assert payload["events"][1]["beat"] is False


def test_earnings_history_endpoint_soft_fails_when_adapter_returns_empty(api_client, monkeypatch):
    """If yfinance has no history (recent IPO, ticker typo) we still want a
    200 with an empty list — the UI renders the friendly empty state. A 5xx
    here would tank the whole earnings panel which is unacceptable."""
    import services.api.app as app_module

    monkeypatch.setattr(app_module, "fetch_earnings_history", lambda ticker, limit=12: [])

    response = api_client.get("/earnings/FOO/history?limit=8")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload == {"ticker": "FOO", "events": []}


def test_market_overview_endpoint_uses_server_side_cache(api_client, monkeypatch):
    import services.api.app as app_module

    calls = {"count": 0}

    def fake_market_overview(ticker, horizon):
        calls["count"] += 1
        return {
            "generated_at": datetime.utcnow(),
            "ticker": ticker,
            "horizon": horizon.value,
            "regime": "risk_on",
            "breadth": "amplio",
            "summary": "Tape constructivo.",
            "warnings": [],
            "instruments": [
                {
                    "symbol": "SPY",
                    "label": "S&P 500",
                    "category": "indices",
                    "price": 500.0,
                    "day_change_pct": 0.01,
                    "relative_to_sma20_pct": 0.02,
                    "relative_to_sma50_pct": 0.03,
                    "tone": "bull",
                    "note": "Arriba de medias.",
                }
            ],
        }

    monkeypatch.setattr(app_module, "_build_market_overview", fake_market_overview)

    first = api_client.get("/market/overview?ticker=AAPL&horizon=short")
    second = api_client.get("/market/overview?ticker=AAPL&horizon=short")

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert calls["count"] == 1
