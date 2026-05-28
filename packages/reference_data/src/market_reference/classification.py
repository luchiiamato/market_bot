"""Hand-maintained sector + region classification for CEDEAR universe tickers.

Why a static table instead of yfinance ``Ticker(symbol).info``?
- ``info`` is slow (one HTTP roundtrip per ticker) and flaky (frequent 429s and
  empty payloads). For the ~60 tickers in ``CEDEAR_UNIVERSE`` the variance is
  effectively zero quarter-over-quarter, so a vetted constant is both faster
  *and* more reliable than scraping.
- A constant also lets us pick the *taxonomy* that makes sense for an AR
  retail investor (e.g. surfacing "Semis" as its own bucket instead of being
  folded into "Technology"), and tag region from a holding perspective
  (Brazilian / Chinese ADRs grouped separately from US large caps).

If a ticker is missing here we fall back to ``{"sector": "Other", "region":
"Unknown"}`` — the UI handles those buckets gracefully and the user still gets
a complete pie of their portfolio.
"""

from __future__ import annotations

from typing import Any, Iterable


# Curated mapping for the CEDEAR universe. Keys are the *underlying* US/global
# tickers (not the BYMA ".BA" variant). Sector taxonomy is intentionally coarse
# so the bar chart stays readable; for a v2 we could split "Software" into
# "AI / data infra" vs "SaaS apps" etc.
TICKER_CLASSIFICATION: dict[str, dict[str, str]] = {
    # --- Mega-caps / index (US / Tech and broad market) ---
    "AAPL": {"sector": "Tech", "region": "US"},
    "AMZN": {"sector": "Consumer", "region": "US"},
    "GOOGL": {"sector": "Tech", "region": "US"},
    "META": {"sector": "Tech", "region": "US"},
    "MSFT": {"sector": "Tech", "region": "US"},
    "NVDA": {"sector": "Semis", "region": "US"},
    "TSLA": {"sector": "Consumer", "region": "US"},
    "QQQ": {"sector": "Index", "region": "US"},
    "SPY": {"sector": "Index", "region": "US"},
    # --- Semis / hardware ---
    "AMD": {"sector": "Semis", "region": "US"},
    "AVGO": {"sector": "Semis", "region": "US"},
    "INTC": {"sector": "Semis", "region": "US"},
    "TSM": {"sector": "Semis", "region": "CN"},
    "ARM": {"sector": "Semis", "region": "US"},
    "MU": {"sector": "Semis", "region": "US"},
    "QCOM": {"sector": "Semis", "region": "US"},
    "ALAB": {"sector": "Semis", "region": "US"},
    # --- AI / cloud / data infra / software ---
    "SNOW": {"sector": "Software", "region": "US"},
    "PLTR": {"sector": "Software", "region": "US"},
    "CRWD": {"sector": "Software", "region": "US"},
    "DDOG": {"sector": "Software", "region": "US"},
    "NET": {"sector": "Software", "region": "US"},
    "MDB": {"sector": "Software", "region": "US"},
    "ZS": {"sector": "Software", "region": "US"},
    "OKTA": {"sector": "Software", "region": "US"},
    "CRM": {"sector": "Software", "region": "US"},
    "ORCL": {"sector": "Software", "region": "US"},
    "ADBE": {"sector": "Software", "region": "US"},
    # --- Fintech / consumer tech ---
    "COIN": {"sector": "Fintech", "region": "US"},
    "PYPL": {"sector": "Fintech", "region": "US"},
    "SHOP": {"sector": "Fintech", "region": "US"},
    "SQ": {"sector": "Fintech", "region": "US"},
    "ABNB": {"sector": "Consumer", "region": "US"},
    "UBER": {"sector": "Consumer", "region": "US"},
    "SPOT": {"sector": "Consumer", "region": "US"},
    # --- Healthcare / pharma ---
    "ABBV": {"sector": "Healthcare", "region": "US"},
    "LLY": {"sector": "Healthcare", "region": "US"},
    "UNH": {"sector": "Healthcare", "region": "US"},
    "IBB": {"sector": "Healthcare", "region": "US"},
    # --- Financials ---
    "JPM": {"sector": "Finance", "region": "US"},
    "BAC": {"sector": "Finance", "region": "US"},
    "BRK.B": {"sector": "Finance", "region": "US"},
    # --- Consumer staples / discretionary ---
    "KO": {"sector": "Consumer", "region": "US"},
    "MCD": {"sector": "Consumer", "region": "US"},
    "WMT": {"sector": "Consumer", "region": "US"},
    "DIS": {"sector": "Consumer", "region": "US"},
    # --- Energy / materials ---
    "XOM": {"sector": "Energy", "region": "US"},
    # --- Argentina (ADRs of locally-operated names) ---
    "GGAL": {"sector": "Finance", "region": "AR"},
    "MELI": {"sector": "Fintech", "region": "AR"},
    "PAM": {"sector": "Energy", "region": "AR"},
    "YPF": {"sector": "Energy", "region": "AR"},
    "VIST": {"sector": "Energy", "region": "AR"},
    # --- Brazil ---
    "PBR": {"sector": "Energy", "region": "BR"},
    "VALE": {"sector": "Materials", "region": "BR"},
    "ABEV": {"sector": "Consumer", "region": "BR"},
    # --- China / EM ---
    "BABA": {"sector": "Consumer", "region": "CN"},
    "BIDU": {"sector": "Tech", "region": "CN"},
    "JD": {"sector": "Consumer", "region": "CN"},
    "PDD": {"sector": "Consumer", "region": "CN"},
    # NU = Nu Holdings, Brazilian neobank but ADR on NYSE; tag as LatAm fintech.
    "NU": {"sector": "Fintech", "region": "BR"},
}


_DEFAULT_CLASSIFICATION: dict[str, str] = {"sector": "Other", "region": "Unknown"}


def classify_ticker(symbol: str) -> dict[str, str]:
    """Return ``{"sector": ..., "region": ...}`` for ``symbol``.

    Unknown tickers fall through to the sentinel ``Other`` / ``Unknown``
    buckets so the UI never has to special-case missing classifications.
    """
    if not symbol:
        return dict(_DEFAULT_CLASSIFICATION)
    normalized = symbol.strip().upper()
    if not normalized:
        return dict(_DEFAULT_CLASSIFICATION)
    return dict(TICKER_CLASSIFICATION.get(normalized, _DEFAULT_CLASSIFICATION))


def aggregate_exposure(
    positions: Iterable[Any],
    key: str,
) -> list[dict]:
    """Group portfolio positions by ``sector`` or ``region`` and rank them.

    ``positions`` is any iterable where each item exposes:
      * ``underlying_ticker`` (str): the canonical US/global symbol used as the
        classification lookup key. CEDEAR positions still resolve to their
        underlying — so 40 AAPL CEDEARs land in the same Tech bucket as 40
        shares of AAPL stock.
      * ``current_value_ars`` (float): the ARS valuation. We sum these to
        compute per-bucket totals and overall portfolio weight.

    Both attribute-style (dataclasses, response models) and dict-style items
    are accepted — the latter so the function can be exercised from tests and
    from the API layer without forcing intermediate conversion.

    ``key`` must be ``"sector"`` or ``"region"``. Anything else raises
    ``ValueError`` rather than silently returning an empty list — a typo here
    would be hard to diagnose downstream.

    Returns a list of ``{"label", "total_value_ars", "pct"}`` dicts sorted by
    ``pct`` descending. Buckets with zero value are dropped (a position with
    ``current_value_ars=0`` shouldn't pollute the legend).
    """
    if key not in {"sector", "region"}:
        raise ValueError(f"key must be 'sector' or 'region', got {key!r}")

    totals: dict[str, float] = {}
    for position in positions:
        ticker = _get(position, "underlying_ticker", default="") or ""
        value = float(_get(position, "current_value_ars", default=0.0) or 0.0)
        if value <= 0:
            continue
        bucket = classify_ticker(ticker)[key]
        totals[bucket] = totals.get(bucket, 0.0) + value

    grand_total = sum(totals.values())
    if grand_total <= 0:
        return []

    buckets = [
        {
            "label": label,
            "total_value_ars": round(value, 2),
            "pct": round(value / grand_total, 4),
        }
        for label, value in totals.items()
    ]
    buckets.sort(key=lambda item: item["pct"], reverse=True)
    return buckets


def _get(obj: Any, name: str, default: Any = None) -> Any:
    """Read ``name`` off ``obj``, supporting both attribute and mapping access."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


__all__ = [
    "TICKER_CLASSIFICATION",
    "classify_ticker",
    "aggregate_exposure",
]
