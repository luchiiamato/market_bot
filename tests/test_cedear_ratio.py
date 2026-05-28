"""``resolve_cedear_reference`` covers four discrete branches.

We unit-test the pure function — no network, no DB. The point is to make
the silent fallback ("ratio_source=fallback_default") explicit so a
regression there can't slip past CI unnoticed.
"""

from __future__ import annotations

from market_portfolio.cedears import resolve_cedear_reference


def test_user_supplied_ratio_wins():
    ref = resolve_cedear_reference(
        symbol="AAPL",
        underlying_ticker="AAPL",
        user_ratio=10.0,
        current_ccl=1200.0,
        local_price_ars=21000.0,
        underlying_price_usd=180.0,
    )
    assert ref.cedear_ratio == 10.0
    assert ref.ratio_source == "user_supplied"
    assert ref.byma_symbol == "AAPL.BA"


def test_parity_match_uses_estimated_ratio():
    # USD * CCL / ratio ≈ local price → ratio = (USD * CCL) / local.
    # For 180 * 1200 / 10 ≈ 21600, choose local 21500 (within tolerance).
    ref = resolve_cedear_reference(
        symbol="AAPL",
        underlying_ticker="AAPL",
        user_ratio=None,
        current_ccl=1200.0,
        local_price_ars=21500.0,
        underlying_price_usd=180.0,
    )
    assert ref.ratio_source == "estimated_market_parity"
    assert ref.cedear_ratio > 0


def test_missing_inputs_fall_back_to_default():
    # Missing CCL (or any leg of the parity formula) → cannot estimate,
    # cannot fail loudly either, so the helper falls back to ratio=1.0.
    ref = resolve_cedear_reference(
        symbol="MELI",
        underlying_ticker="MELI",
        user_ratio=None,
        current_ccl=None,
        local_price_ars=None,
        underlying_price_usd=None,
    )
    assert ref.ratio_source == "fallback_default"
    assert ref.cedear_ratio == 1.0


def test_parity_miss_uses_unbounded_estimate():
    # When parity is far from any canonical ratio, the helper still
    # returns the raw parity number (clamped to ≥1) — this is documented
    # behaviour, not fallback_default.
    ref = resolve_cedear_reference(
        symbol="MELI",
        underlying_ticker="MELI",
        user_ratio=None,
        current_ccl=1200.0,
        local_price_ars=999_999.0,
        underlying_price_usd=180.0,
    )
    assert ref.ratio_source == "estimated_market_parity"
    assert ref.cedear_ratio >= 1.0


def test_underlying_ticker_inferred_from_symbol_when_missing():
    ref = resolve_cedear_reference(
        symbol="TSLA",
        underlying_ticker=None,
        user_ratio=5.0,
        current_ccl=None,
        local_price_ars=None,
        underlying_price_usd=None,
    )
    assert ref.underlying_ticker == "TSLA"


def test_byma_symbol_strips_trailing_ba_suffix():
    ref = resolve_cedear_reference(
        symbol="NVDA.BA",
        underlying_ticker="NVDA",
        user_ratio=20.0,
        current_ccl=None,
        local_price_ars=None,
        underlying_price_usd=None,
    )
    # build_byma_symbol normalises both .BA and dot variations.
    assert ref.byma_symbol == "NVDA.BA"
