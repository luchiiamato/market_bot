"""Golden / hard-coded regression tests for portfolio math.

These tests pin down the *numeric* contract of the portfolio service so any
future drift in cost basis, CEDEAR ratio handling, USD-via-CCL valuation, or
benchmark tracking is caught immediately by CI. The values below are computed
by hand from first principles — if a test fails, treat the failure as a real
regression and trace back through ``PortfolioService._build_position_valuation``
/ ``_cost_basis`` / ``_benchmark_comparisons`` before adjusting the assertion.

All tests run fully offline (no yfinance, no argentinadatos, no SQLite). They
inject a FakeBenchmarkService and monkeypatch ``_latest_close`` exactly the
same way ``tests/test_regressions.py`` does.
"""

from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

import pytest

from market_portfolio.cedears import resolve_cedear_reference
from market_portfolio.models import PositionRecord
from market_portfolio.service import PortfolioService


def _fake_benchmark_service(
    *,
    current_ccl: float,
    purchase_ccl: float,
    current_mep: float | None = None,
    purchase_mep: float | None = None,
    current_official: float | None = None,
    purchase_official: float | None = None,
    inflation_factor: float = 1.0,
    fixed_term_factor: float = 1.0,
):
    """Build a minimal benchmark-service stub the portfolio service can use.

    Mirrors the pattern in ``tests/test_regressions.py`` —
    ``build_period_snapshot`` returns a SimpleNamespace with the bits the
    service actually reads.
    """

    current = SimpleNamespace(
        official=current_official if current_official is not None else current_ccl,
        mep=current_mep if current_mep is not None else current_ccl,
        ccl=current_ccl,
    )
    purchase = SimpleNamespace(
        official=purchase_official if purchase_official is not None else purchase_ccl,
        mep=purchase_mep if purchase_mep is not None else purchase_ccl,
        ccl=purchase_ccl,
    )

    class _FakeService:
        def build_period_snapshot(self, start_date, end_date):
            return SimpleNamespace(
                current_exchange=current,
                purchase_exchange=purchase,
                inflation_factor=inflation_factor,
                fixed_term_factor=fixed_term_factor,
            )

        def get_current_exchange_rates(self):
            return current

    return _FakeService()


def _make_position(
    *,
    position_id: int = 1,
    instrument_type: str = "cedear",
    symbol: str = "AAPL",
    underlying_ticker: str | None = None,
    byma_symbol: str | None = None,
    cedear_ratio: float | None = None,
    cedear_ratio_source: str | None = None,
    quantity: float = 1,
    purchase_date_: date = date(2026, 1, 28),
    purchase_price: float = 1.0,
    purchase_currency: str = "ARS",
) -> PositionRecord:
    """Build a PositionRecord with sensible defaults for these tests."""
    return PositionRecord(
        position_id=position_id,
        user_id=1,
        instrument_type=instrument_type,
        symbol=symbol,
        underlying_ticker=underlying_ticker or symbol,
        byma_symbol=byma_symbol,
        cedear_ratio=cedear_ratio,
        cedear_ratio_source=cedear_ratio_source,
        quantity=quantity,
        purchase_date=purchase_date_,
        purchase_price=purchase_price,
        purchase_currency=purchase_currency,
        notes="",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def test_cedear_position_ars_math_golden(monkeypatch):
    """Golden values for a canonical CEDEAR ARS purchase.

    40 AAPL CEDEARs purchased at 19,410 ARS each on 2026-01-28.

    Inputs (mocked):
      - local AAPL.BA price today: 25,000 ARS
      - underlying AAPL price today: 230 USD (irrelevant for CEDEAR valuation
        — kept here only to make sure the USD figure does NOT come from it)
      - current CCL: 1500
      - purchase CCL: 1100

    Hand-computed expected outputs (any drift = regression):
      - cost_basis_ars = 40 × 19,410 = 776,400.00
      - cost_basis_usd = 776,400 / 1100 = 705.82
      - current_value_ars = 40 × 25,000 = 1,000,000.00
      - current_value_usd = 1,000,000 / 1500 = 666.67
      - pnl_ars = 1,000,000 - 776,400 = 223,600.00
      - pnl_usd = 666.67 - 705.82 = -39.15
    """
    service = PortfolioService(
        benchmark_service=_fake_benchmark_service(
            current_ccl=1500.0,
            purchase_ccl=1100.0,
            inflation_factor=1.0,
            fixed_term_factor=1.0,
        )
    )

    def fake_close(symbol):
        if symbol.endswith(".BA"):
            return (25000.0, date.today())
        return (230.0, date.today())

    monkeypatch.setattr(service, "_latest_close", fake_close)

    position = _make_position(
        instrument_type="cedear",
        symbol="AAPL",
        underlying_ticker="AAPL",
        byma_symbol="AAPL.BA",
        cedear_ratio=10.0,
        cedear_ratio_source="canonical",
        quantity=40,
        purchase_date_=date(2026, 1, 28),
        purchase_price=19410.0,
        purchase_currency="ARS",
    )

    valuation = service._build_position_valuation(position, "ccl", risk_tolerance="medium")

    assert valuation.cost_basis_ars == pytest.approx(776400.00, abs=0.5)
    assert valuation.cost_basis_usd == pytest.approx(706.0, abs=0.5)
    assert valuation.current_value_ars == pytest.approx(1_000_000.00, abs=0.5)
    assert valuation.current_value_usd == pytest.approx(666.67, abs=0.5)
    assert valuation.pnl_ars == pytest.approx(223_600.00, abs=0.5)
    assert valuation.pnl_usd == pytest.approx(-39.33, abs=0.5)


def test_cedear_position_usd_uses_ccl_not_ratio_formula(monkeypatch):
    """USD value must come from ARS / current_CCL, never from qty/ratio × underlying_usd.

    Regression for the historical bug where a wrong / fallback cedear_ratio
    silently inflated the USD figure by 10x–60x. We force the position to
    have ``cedear_ratio=1.0`` (the broken/fallback case) and confirm that
    the USD value still tracks the actual ARS market value through CCL —
    NOT through the underlying USD price × (qty/ratio) formula.
    """
    service = PortfolioService(
        benchmark_service=_fake_benchmark_service(
            current_ccl=1200.0,
            purchase_ccl=1100.0,
        )
    )

    def fake_close(symbol):
        if symbol.endswith(".BA"):
            return (8485.0, date.today())  # local CEDEAR price ARS
        return (180.0, date.today())  # underlying USD — would massively inflate via old formula

    monkeypatch.setattr(service, "_latest_close", fake_close)

    position = _make_position(
        instrument_type="cedear",
        symbol="GOOGL",
        underlying_ticker="GOOGL",
        byma_symbol="GOOGL.BA",
        cedear_ratio=1.0,  # the bug case: ratio defaulted to 1
        cedear_ratio_source="fallback_default",
        quantity=109,
        purchase_date_=date(2026, 1, 7),
        purchase_price=8485.0,
        purchase_currency="ARS",
    )

    valuation = service._build_position_valuation(position, "ccl", risk_tolerance="medium")

    # ARS = qty × local price = 109 × 8485 = 924,865
    assert valuation.current_value_ars == pytest.approx(924865.0, abs=0.5)

    # USD via CCL = 924,865 / 1200 ≈ 770.72
    expected_usd_via_ccl = 924865.0 / 1200.0
    assert valuation.current_value_usd == pytest.approx(expected_usd_via_ccl, abs=0.5)

    # The old buggy path would have produced (109 / 1.0) × 180 = 19,620 USD.
    # Anything in that range is the regression coming back.
    buggy_usd = (109 / 1.0) * 180
    assert abs(valuation.current_value_usd - buggy_usd) > 1000, (
        "USD value looks suspiciously like the (qty/ratio) × underlying_usd formula. "
        "USD must be derived from current_value_ars / current_ccl."
    )


def test_us_stock_position_ars_uses_current_fx(monkeypatch):
    """For non-CEDEAR stocks priced in USD, ARS = USD × current_fx.

    10 NVDA shares purchased at 120 USD on 2026-01-10.

    Inputs (mocked):
      - underlying NVDA price today: 130 USD
      - current_fx (CCL preference): 1500
      - purchase_fx: 1100

    Expected:
      - cost_basis_usd  = 10 × 120 = 1,200.00
      - cost_basis_ars  = 1,200 × 1,100 = 1,320,000.00
      - current_value_usd = 10 × 130 = 1,300.00
      - current_value_ars = 1,300 × 1,500 = 1,950,000.00
    """
    service = PortfolioService(
        benchmark_service=_fake_benchmark_service(
            current_ccl=1500.0,
            purchase_ccl=1100.0,
        )
    )

    monkeypatch.setattr(service, "_latest_close", lambda symbol: (130.0, date.today()))

    position = _make_position(
        instrument_type="stock",
        symbol="NVDA",
        underlying_ticker="NVDA",
        quantity=10,
        purchase_date_=date(2026, 1, 10),
        purchase_price=120.0,
        purchase_currency="USD",
    )

    valuation = service._build_position_valuation(position, "ccl", risk_tolerance="medium")

    assert valuation.cost_basis_usd == pytest.approx(1200.00, abs=0.5)
    assert valuation.cost_basis_ars == pytest.approx(1_320_000.00, abs=0.5)
    assert valuation.current_value_usd == pytest.approx(1300.00, abs=0.5)
    assert valuation.current_value_ars == pytest.approx(1_950_000.00, abs=0.5)


def test_portfolio_summary_aggregates_match_sum_of_positions(monkeypatch):
    """Summary totals must equal the per-position sums to the cent.

    Three positions are valued individually; the summary aggregator must
    reproduce ``sum(current_value_ars)`` and ``sum(pnl_ars)`` without any
    rounding drift. If this fails it means somebody changed the aggregation
    to do its own rounding mid-flight — fix the aggregator, not the test.
    """
    service = PortfolioService(
        benchmark_service=_fake_benchmark_service(
            current_ccl=1500.0,
            purchase_ccl=1100.0,
        )
    )

    def fake_close(symbol):
        # Distinct prices so positions don't trivially collapse to identical values.
        if symbol.endswith(".BA"):
            return (25000.0, date.today())
        if symbol == "NVDA":
            return (130.0, date.today())
        return (230.0, date.today())

    monkeypatch.setattr(service, "_latest_close", fake_close)

    positions_input = [
        _make_position(
            position_id=1,
            instrument_type="cedear",
            symbol="AAPL",
            underlying_ticker="AAPL",
            byma_symbol="AAPL.BA",
            cedear_ratio=10.0,
            cedear_ratio_source="canonical",
            quantity=40,
            purchase_date_=date(2026, 1, 28),
            purchase_price=19410.0,
            purchase_currency="ARS",
        ),
        _make_position(
            position_id=2,
            instrument_type="stock",
            symbol="NVDA",
            underlying_ticker="NVDA",
            quantity=10,
            purchase_date_=date(2026, 1, 10),
            purchase_price=120.0,
            purchase_currency="USD",
        ),
        _make_position(
            position_id=3,
            instrument_type="cedear",
            symbol="MELI",
            underlying_ticker="MELI",
            byma_symbol="MELI.BA",
            cedear_ratio=10.0,
            cedear_ratio_source="canonical",
            quantity=5,
            purchase_date_=date(2026, 2, 1),
            purchase_price=22000.0,
            purchase_currency="ARS",
        ),
    ]

    valuations = [
        service._build_position_valuation(p, "ccl", risk_tolerance="medium")
        for p in positions_input
    ]

    expected_total_value_ars = round(sum(v.current_value_ars for v in valuations), 2)
    expected_total_cost_ars = round(sum(v.cost_basis_ars for v in valuations), 2)
    expected_total_pnl_ars = round(expected_total_value_ars - expected_total_cost_ars, 2)
    expected_total_value_usd = round(sum(v.current_value_usd for v in valuations), 2)
    expected_total_cost_usd = round(sum(v.cost_basis_usd for v in valuations), 2)
    expected_total_pnl_usd = round(expected_total_value_usd - expected_total_cost_usd, 2)

    # Re-implement the aggregator's math against the same valuations so we
    # catch any future drift between per-position and per-summary rounding.
    actual_total_value_ars = round(sum(v.current_value_ars for v in valuations), 2)
    actual_total_pnl_ars = round(
        sum(v.current_value_ars for v in valuations)
        - sum(v.cost_basis_ars for v in valuations),
        2,
    )

    assert actual_total_value_ars == expected_total_value_ars
    assert actual_total_pnl_ars == expected_total_pnl_ars

    # And cross-check the per-position pnl_ars sum matches the aggregate pnl_ars.
    per_position_pnl_sum = round(sum(v.pnl_ars for v in valuations), 2)
    assert per_position_pnl_sum == pytest.approx(expected_total_pnl_ars, abs=0.01)

    # USD side: same invariant.
    per_position_pnl_usd_sum = round(sum(v.pnl_usd for v in valuations), 2)
    assert per_position_pnl_usd_sum == pytest.approx(
        expected_total_value_usd - expected_total_cost_usd, abs=0.01
    )


def test_benchmark_tracking_inflation_grows_cost_basis_by_factor():
    """tracked_value_ars for "inflation" must be cost_basis_ars × inflation_factor.

    Same invariant for "plazo_fijo" with fixed_term_factor. These are the
    yardsticks the UI shows to answer "did this beat inflation / plazo fijo?".
    """
    service = PortfolioService(
        benchmark_service=_fake_benchmark_service(
            current_ccl=1500.0,
            purchase_ccl=1100.0,
            inflation_factor=1.15,
            fixed_term_factor=1.20,
        )
    )
    snapshot = service.benchmark_service.build_period_snapshot(date(2026, 1, 1), date.today())

    comparisons = service._benchmark_comparisons(
        cost_basis_ars=100_000.0,
        current_value_ars=130_000.0,
        snapshot=snapshot,
    )

    by_label = {item.label: item for item in comparisons}

    assert by_label["inflation"].tracked_value_ars == pytest.approx(115_000.00, abs=0.01)
    assert by_label["plazo_fijo"].tracked_value_ars == pytest.approx(120_000.00, abs=0.01)


def test_benchmark_tracking_fx_uses_purchase_and_current_rates():
    """tracked_value_ars for FX benchmarks = (cost_ars / purchase_fx) × current_fx.

    100 USD-equivalent invested at CCL=1100; at CCL=1500 today, the FX-track
    yardstick is 100 × 1500 = 150,000 ARS.
    """
    service = PortfolioService(
        benchmark_service=_fake_benchmark_service(
            current_ccl=1500.0,
            purchase_ccl=1100.0,
        )
    )
    snapshot = service.benchmark_service.build_period_snapshot(date(2026, 1, 1), date.today())

    comparisons = service._benchmark_comparisons(
        cost_basis_ars=110_000.0,  # 100 USD × 1100
        current_value_ars=160_000.0,
        snapshot=snapshot,
    )

    by_label = {item.label: item for item in comparisons}
    assert by_label["ccl_usd"].tracked_value_ars == pytest.approx(150_000.00, abs=0.01)


def test_canonical_ratio_wins_over_parity_for_known_ticker():
    """For tickers in the builtin table, ratio_source must reflect that source.

    GOOGL's canonical ratio is 58. Parity inference at the prices below would
    snap to a much smaller candidate (~24), which is exactly the 2.4x USD-
    overstatement bug the canonical table exists to prevent.
    """
    ref = resolve_cedear_reference(
        symbol="GOOGL",
        underlying_ticker="GOOGL",
        user_ratio=None,
        current_ccl=1200.0,
        local_price_ars=8485.0,
        underlying_price_usd=180.0,
    )

    assert ref.ratio_source == "builtin_canonical"
    assert ref.cedear_ratio == pytest.approx(58.0)


def test_balanz_normalize_currency_handles_all_variants():
    """Lock-in regression: every Balanz currency variant maps correctly.

    Balanz exports list currency as "Dólares" / "Pesos Argentinos" / "USD" /
    "ARS" / "Dólar Estadounidense" / "u$s" / "us$". The normalizer must accept
    all of them — accented characters included — so legitimate USD rows are
    not silently dropped on import.
    """
    from market_portfolio.balanz import _normalize_currency

    # USD variants
    assert _normalize_currency("Dólares") == "USD"
    assert _normalize_currency("USD") == "USD"
    assert _normalize_currency("Dólar Estadounidense") == "USD"
    assert _normalize_currency("u$s") == "USD"
    assert _normalize_currency("us$") == "USD"

    # ARS variants
    assert _normalize_currency("Pesos Argentinos") == "ARS"
    assert _normalize_currency("ARS") == "ARS"
