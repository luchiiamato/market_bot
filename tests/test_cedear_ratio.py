"""``resolve_cedear_reference`` covers four discrete branches.

We unit-test the pure function — no network, no DB. The point is to make
the silent fallback ("ratio_source=fallback_default") explicit so a
regression there can't slip past CI unnoticed.
"""

from __future__ import annotations

import importlib

from market_portfolio.cedears import (
    build_byma_symbol,
    canonical_cedear_ratio,
    clear_cedear_catalog_cache,
    resolve_cedear_reference,
    to_market_data_symbol,
)


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


def test_canonical_table_beats_parity_inference():
    # AAPL is in CANONICAL_CEDEAR_RATIOS (10:1). Even if parity inference
    # would suggest a different snap-to ratio, canonical wins — this is the
    # whole point of the table: stop the silent 2-3x USD overstatement that
    # came from inference picking the wrong neighbour for tickers like GOOGL.
    ref = resolve_cedear_reference(
        symbol="AAPL",
        underlying_ticker="AAPL",
        user_ratio=None,
        current_ccl=1200.0,
        local_price_ars=21500.0,
        underlying_price_usd=180.0,
    )
    assert ref.ratio_source == "builtin_canonical"
    # AAPL canonical ratio is 20:1 (market-validated 2026-05, was a wrong 10 guess).
    assert ref.cedear_ratio == 20.0


def test_parity_match_uses_estimated_ratio_for_unknown_ticker():
    # ``ZZZTEST`` is not in the canonical table — falls through to parity.
    ref = resolve_cedear_reference(
        symbol="ZZZTEST",
        underlying_ticker="ZZZTEST",
        user_ratio=None,
        current_ccl=1200.0,
        local_price_ars=21500.0,
        underlying_price_usd=180.0,
    )
    assert ref.ratio_source == "estimated_market_parity"
    assert ref.cedear_ratio > 0


def test_missing_inputs_fall_back_to_default_for_unknown_ticker():
    # ``ZZZ`` is not in the canonical table and we have no price legs, so
    # the helper falls back to ratio=1.0 with an explicit source so the UI
    # can flag it. Note: known tickers (MELI, AAPL, ...) would hit canonical
    # before this path.
    ref = resolve_cedear_reference(
        symbol="ZZZ",
        underlying_ticker="ZZZ",
        user_ratio=None,
        current_ccl=None,
        local_price_ars=None,
        underlying_price_usd=None,
    )
    assert ref.ratio_source == "fallback_default"
    assert ref.cedear_ratio == 1.0


def test_parity_miss_uses_unbounded_estimate_for_unknown_ticker():
    # When parity is far from any common candidate AND the ticker isn't in
    # the canonical table, fall back to the raw parity number (clamped to ≥1).
    ref = resolve_cedear_reference(
        symbol="ZZZTEST",
        underlying_ticker="ZZZTEST",
        user_ratio=None,
        current_ccl=1200.0,
        local_price_ars=999_999.0,
        underlying_price_usd=180.0,
    )
    assert ref.ratio_source == "estimated_market_parity"
    assert ref.cedear_ratio >= 1.0


def test_known_ticker_hits_canonical_even_without_price_legs():
    # MELI is in canonical (120:1, market-validated 2026-05). Without price legs,
    # we'd previously fall straight to fallback_default. The canonical layer stops that.
    ref = resolve_cedear_reference(
        symbol="MELI",
        underlying_ticker="MELI",
        user_ratio=None,
        current_ccl=None,
        local_price_ars=None,
        underlying_price_usd=None,
    )
    assert ref.ratio_source == "builtin_canonical"
    assert ref.cedear_ratio == 120.0


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


def test_external_reference_file_overrides_builtin_ratio(tmp_path, monkeypatch):
    reference_file = tmp_path / "cedears.csv"
    reference_file.write_text(
        "Ticker,Empresa,Ratio,Pais,Sector,Tipo,ISIN CEDEAR\n"
        "AAPL,APPLE INC.,20:1,Estados Unidos,Tecnologia,CEDEAR,ARTEST0001\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MARKET_BOT_CEDEAR_REFERENCE_FILE", str(reference_file))
    clear_cedear_catalog_cache()
    try:
        assert canonical_cedear_ratio("AAPL") == 20.0
        ref = resolve_cedear_reference(
            symbol="AAPL",
            underlying_ticker="AAPL",
            user_ratio=None,
            current_ccl=None,
            local_price_ars=None,
            underlying_price_usd=None,
        )
        assert ref.ratio_source == "reference_file"
        assert ref.cedear_ratio == 20.0
    finally:
        monkeypatch.delenv("MARKET_BOT_CEDEAR_REFERENCE_FILE", raising=False)
        clear_cedear_catalog_cache()


def test_external_reference_file_keeps_distinct_ratios_per_ticker(tmp_path, monkeypatch):
    reference_file = tmp_path / "cedears.csv"
    reference_file.write_text(
        "Ticker,Empresa,Ratio,Pais,Sector,Tipo,ISIN CEDEAR\n"
        "AAPL,APPLE INC.,20:1,Estados Unidos,Tecnologia,CEDEAR,ARTEST0001\n"
        "MSFT,MICROSOFT CORP.,30:1,Estados Unidos,Tecnologia,CEDEAR,ARTEST0002\n"
        "MELI,MERCADOLIBRE INC.,120:1,Argentina,Consumo,CEDEAR,ARTEST0003\n"
        "BRK/B,BERKSHIRE HATHAWAY,22:1,Estados Unidos,Finanzas,CEDEAR,ARTEST0004\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MARKET_BOT_CEDEAR_REFERENCE_FILE", str(reference_file))
    clear_cedear_catalog_cache()
    try:
        assert canonical_cedear_ratio("AAPL") == 20.0
        assert canonical_cedear_ratio("MSFT") == 30.0
        assert canonical_cedear_ratio("MELI") == 120.0
        assert canonical_cedear_ratio("BRK/B") == 22.0
        assert len(
            {
                canonical_cedear_ratio("AAPL"),
                canonical_cedear_ratio("MSFT"),
                canonical_cedear_ratio("MELI"),
                canonical_cedear_ratio("BRK/B"),
            }
        ) == 4
    finally:
        monkeypatch.delenv("MARKET_BOT_CEDEAR_REFERENCE_FILE", raising=False)
        clear_cedear_catalog_cache()


def test_share_class_symbols_normalize_for_byma_and_market_data():
    assert build_byma_symbol("BRK/B") == "BRKB.BA"
    assert build_byma_symbol("BRK.B") == "BRKB.BA"
    assert to_market_data_symbol("BRK/B") == "BRK-B"
    assert to_market_data_symbol("BRK.B") == "BRK-B"


def test_engine_detects_external_cedear_without_expanding_static_universe(tmp_path, monkeypatch):
    reference_file = tmp_path / "cedears.csv"
    reference_file.write_text(
        "Ticker,Empresa,Ratio,Pais,Sector,Tipo,ISIN CEDEAR\n"
        "TLT,ISHARES 20+ YEAR TREASURY BOND ETF,4:1,Estados Unidos,Renta fija,CEDEAR,ARTEST0005\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MARKET_BOT_CEDEAR_REFERENCE_FILE", str(reference_file))
    clear_cedear_catalog_cache()
    try:
        import market_bot.config as market_config

        market_config = importlib.reload(market_config)
        assert market_config.is_cedear_ticker("TLT") is True
        assert "TLT" not in market_config.CEDEAR_UNIVERSE
    finally:
        monkeypatch.delenv("MARKET_BOT_CEDEAR_REFERENCE_FILE", raising=False)
        clear_cedear_catalog_cache()
        import market_bot.config as market_config

        importlib.reload(market_config)
