"""Tests for sector + region exposure aggregation.

The aggregator powers the concentration bars in the portfolio summary view.
The math is trivial — sum ARS per bucket, divide by total — but it has to
hold up against the same shapes the API and the service return:
``PositionValuation`` dataclasses, response models, and plain dicts.
"""

from __future__ import annotations

import pytest

from market_reference.classification import (
    TICKER_CLASSIFICATION,
    aggregate_exposure,
    classify_ticker,
)


def _pos(ticker: str, value_ars: float) -> dict:
    """Minimal positions shape — only the two fields ``aggregate_exposure`` reads."""
    return {"underlying_ticker": ticker, "current_value_ars": value_ars}


def test_classify_ticker_known_and_unknown():
    aapl = classify_ticker("AAPL")
    assert aapl == {"sector": "Tech", "region": "US"}

    # Normalization: lowercase + whitespace
    assert classify_ticker(" aapl ") == {"sector": "Tech", "region": "US"}

    # Argentina ADRs land in AR region
    assert classify_ticker("MELI")["region"] == "AR"
    assert classify_ticker("YPF") == {"sector": "Energy", "region": "AR"}

    # Unknown -> Other / Unknown sentinel
    assert classify_ticker("ZZZZ") == {"sector": "Other", "region": "Unknown"}
    assert classify_ticker("") == {"sector": "Other", "region": "Unknown"}


def test_aggregate_exposure_by_sector_sorted_and_normalized():
    """60/20/20 split across three sectors -> sorted desc, pcts sum to 1.0."""
    positions = [
        _pos("AAPL", 600_000),   # Tech
        _pos("NVDA", 100_000),   # Semis
        _pos("AMD", 100_000),    # Semis
        _pos("JPM", 200_000),    # Finance
    ]
    buckets = aggregate_exposure(positions, "sector")

    # 3 distinct sectors -> Tech 60%, Finance 20%, Semis 20%.
    labels = [b["label"] for b in buckets]
    assert labels[0] == "Tech"
    assert {"Tech", "Finance", "Semis"} == set(labels)

    by_label = {b["label"]: b for b in buckets}
    assert by_label["Tech"]["total_value_ars"] == pytest.approx(600_000.0)
    assert by_label["Tech"]["pct"] == pytest.approx(0.60, abs=1e-4)
    assert by_label["Finance"]["pct"] == pytest.approx(0.20, abs=1e-4)
    assert by_label["Semis"]["pct"] == pytest.approx(0.20, abs=1e-4)

    # Sorted descending by pct (Tech first, then a tie between Finance & Semis).
    pcts = [b["pct"] for b in buckets]
    assert pcts == sorted(pcts, reverse=True)
    assert sum(pcts) == pytest.approx(1.0, abs=1e-3)


def test_aggregate_exposure_by_region_groups_argentina_and_unknown():
    """AR ADRs land in AR; unknown tickers fall through to ``Unknown``."""
    positions = [
        _pos("AAPL", 400_000),   # US
        _pos("MELI", 200_000),   # AR
        _pos("YPF", 100_000),    # AR
        _pos("ZZZZ", 300_000),   # Unknown
    ]
    buckets = aggregate_exposure(positions, "region")
    by_label = {b["label"]: b for b in buckets}

    assert by_label["US"]["pct"] == pytest.approx(0.40, abs=1e-4)
    assert by_label["AR"]["total_value_ars"] == pytest.approx(300_000.0)
    assert by_label["AR"]["pct"] == pytest.approx(0.30, abs=1e-4)
    assert by_label["Unknown"]["pct"] == pytest.approx(0.30, abs=1e-4)

    # Empty / zero-value positions drop out — they shouldn't pollute the chart.
    buckets_with_zero = aggregate_exposure(
        positions + [_pos("SPY", 0.0)],
        "region",
    )
    assert "Index" not in {b["label"] for b in buckets_with_zero}


def test_aggregate_exposure_empty_and_invalid_key():
    assert aggregate_exposure([], "sector") == []
    assert aggregate_exposure([_pos("AAPL", 0.0)], "sector") == []

    with pytest.raises(ValueError):
        aggregate_exposure([_pos("AAPL", 100.0)], "invalid_key")


def test_classification_coverage_of_cedear_universe():
    """Every ticker in ``CEDEAR_UNIVERSE`` must be classified — no silent fallthrough.

    A missing classification means the UI would show "Other / Unknown" for a
    known holding, which is exactly the bug this table exists to prevent.
    """
    from market_bot.config import CEDEAR_UNIVERSE

    missing = [t for t in CEDEAR_UNIVERSE if t.upper() not in TICKER_CLASSIFICATION]
    assert not missing, f"CEDEAR tickers without classification: {missing}"
