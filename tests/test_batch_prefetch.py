"""Offline tests for the batched yfinance prefetch paths.

Covers two performance-critical hot paths added to cut /portfolio/summary
and /rankings latency:

1. ``PortfolioService.prefetch_quotes`` — one ``yf.download`` for every
   BYMA + underlying symbol used by a user's positions, warming the
   ``_quote_cache`` so the per-position ``_latest_close`` calls become
   pure cache hits.
2. ``YFinanceMarketDataAdapter.prefetch_universe`` — one ``yf.download``
   for the ranking universe, warming ``_price_cache`` so each ranker
   worker reads from cache instead of hitting yfinance individually.

Both methods must:
  - parse the MultiIndex column shape that ``yf.download`` returns for
    multi-ticker requests,
  - tolerate missing tickers in the response,
  - never raise on a failure (best-effort warmup).
"""

from __future__ import annotations

import sys
from datetime import date

import pandas as pd
import pytest


def _make_multi_ticker_frame(tickers: list[str]) -> pd.DataFrame:
    """Return a frame shaped like ``yf.download(..., group_by='ticker')``.

    Top-level column index = ticker, second level = field.
    """
    index = pd.date_range("2026-01-20", periods=3, freq="D")
    frames = {}
    for i, ticker in enumerate(tickers):
        base = 100.0 + i * 10
        frames[ticker] = pd.DataFrame(
            {
                "Open": [base, base + 1, base + 2],
                "High": [base + 2, base + 3, base + 4],
                "Low": [base - 1, base, base + 1],
                "Close": [base + 1, base + 2, base + 3],
                "Volume": [1_000_000, 1_100_000, 1_200_000],
            },
            index=index,
        )
    return pd.concat(frames, axis=1)


def test_portfolio_prefetch_quotes_warms_cache_from_multi_ticker_frame(monkeypatch):
    """A multi-ticker yf.download response must populate _quote_cache for every symbol."""
    from market_portfolio.service import PortfolioService

    service = PortfolioService.__new__(PortfolioService)
    from market_bot.utils import TTLCache

    service._quote_cache = TTLCache(ttl_seconds=900)

    captured: dict[str, object] = {}

    def fake_download(tickers, **kwargs):
        captured["tickers"] = tickers
        captured["kwargs"] = kwargs
        return _make_multi_ticker_frame(["AAPL", "AAPL.BA", "GOOGL"])

    monkeypatch.setitem(sys.modules, "yfinance", type(sys)("yfinance"))
    sys.modules["yfinance"].download = fake_download  # type: ignore[attr-defined]

    service.prefetch_quotes(["AAPL", "AAPL.BA", "GOOGL"])

    # All three should be cached.
    assert service._quote_cache.get("AAPL") is not None
    assert service._quote_cache.get("AAPL.BA") is not None
    assert service._quote_cache.get("GOOGL") is not None

    # Latest close for AAPL (index 0): base=100, last Close = 103.
    price, quote_date = service._quote_cache.get("AAPL")
    assert price == pytest.approx(103.0)
    assert isinstance(quote_date, date)

    # group_by=ticker must be passed so the column shape is predictable.
    assert captured["kwargs"]["group_by"] == "ticker"


def test_portfolio_prefetch_quotes_handles_missing_ticker(monkeypatch):
    """A symbol absent from the batch response must be silently skipped."""
    from market_portfolio.service import PortfolioService
    from market_bot.utils import TTLCache

    service = PortfolioService.__new__(PortfolioService)
    service._quote_cache = TTLCache(ttl_seconds=900)

    def fake_download(tickers, **kwargs):
        # Only return data for two of the three requested.
        return _make_multi_ticker_frame(["AAPL", "GOOGL"])

    monkeypatch.setitem(sys.modules, "yfinance", type(sys)("yfinance"))
    sys.modules["yfinance"].download = fake_download  # type: ignore[attr-defined]

    service.prefetch_quotes(["AAPL", "GOOGL", "MISSING"])

    assert service._quote_cache.get("AAPL") is not None
    assert service._quote_cache.get("GOOGL") is not None
    assert service._quote_cache.get("MISSING") is None


def test_portfolio_prefetch_quotes_swallows_download_exception(monkeypatch):
    """Any error from yf.download must not propagate."""
    from market_portfolio.service import PortfolioService
    from market_bot.utils import TTLCache

    service = PortfolioService.__new__(PortfolioService)
    service._quote_cache = TTLCache(ttl_seconds=900)

    def fake_download(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setitem(sys.modules, "yfinance", type(sys)("yfinance"))
    sys.modules["yfinance"].download = fake_download  # type: ignore[attr-defined]

    # Must not raise.
    service.prefetch_quotes(["AAPL"])
    assert service._quote_cache.get("AAPL") is None


def test_engine_prefetch_universe_warms_price_cache(monkeypatch):
    """Adapter prefetch must populate _price_cache for the full universe."""
    from market_bot.contracts import Horizon
    from market_bot.data import YFinanceMarketDataAdapter

    adapter = YFinanceMarketDataAdapter()

    # Build a frame with enough rows to exceed the smallest warmup_bars
    # requirement. We grow the per-ticker frames to 250 days so any
    # horizon's warmup gate (max 200) is satisfied.
    tickers = ["AAPL", "GOOGL", "NVDA"]
    index = pd.date_range("2025-01-01", periods=260, freq="B")
    frames = {}
    for i, ticker in enumerate(tickers):
        base = 100.0 + i * 10
        frames[ticker] = pd.DataFrame(
            {
                "Open": [base] * len(index),
                "High": [base + 1] * len(index),
                "Low": [base - 1] * len(index),
                "Close": [base + 0.5] * len(index),
                "Volume": [1_000_000] * len(index),
            },
            index=index,
        )
    fake_frame = pd.concat(frames, axis=1)

    def fake_download(targets, **kwargs):
        assert kwargs.get("group_by") == "ticker"
        return fake_frame

    monkeypatch.setitem(sys.modules, "yfinance", type(sys)("yfinance"))
    sys.modules["yfinance"].download = fake_download  # type: ignore[attr-defined]

    adapter.prefetch_universe(tickers, Horizon.SHORT)

    for t in tickers:
        cached = adapter._price_cache.get((t, Horizon.SHORT.value))
        assert cached is not None
        assert not cached.frame.empty
        # Required columns present and numeric.
        for col in ("Open", "High", "Low", "Close", "Volume"):
            assert col in cached.frame.columns
