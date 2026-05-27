"""Earnings calendar adapter.

We use ``yfinance``'s :meth:`Ticker.get_earnings_dates` accessor, which returns
a small dataframe with date/EPS estimate/EPS actual rows. Free, no API key.

The sync function persists into ``earnings_calendar`` and is idempotent.
Stale-while-revalidate window is 24h — earnings calendars don't change
intra-day, so refetching more often is waste.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable

import pandas as pd

from .earnings_store import (
    latest_fetch_at,
    list_upcoming,
    next_earnings_date,
    upsert_earnings,
)


class EarningsIngestionError(RuntimeError):
    """Raised when the earnings adapter cannot fetch."""


CACHE_TTL_SECONDS = 24 * 60 * 60


@dataclass
class EarningsEvent:
    ticker: str
    report_date: date
    report_time: str | None
    eps_estimate: float | None
    eps_actual: float | None
    revenue_estimate: float | None
    revenue_actual: float | None


def _is_cache_fresh(ticker: str) -> bool:
    last = latest_fetch_at(ticker)
    if last is None:
        return False
    return (datetime.utcnow() - last).total_seconds() < CACHE_TTL_SECONDS


def _fetch_via_yfinance(ticker: str) -> list[dict]:
    try:
        import yfinance as yf
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise EarningsIngestionError("yfinance is required for earnings ingestion") from exc

    try:
        frame = yf.Ticker(ticker).get_earnings_dates(limit=12)
    except Exception as exc:  # pragma: no cover
        raise EarningsIngestionError(f"yfinance earnings failed for {ticker}: {exc}") from exc

    if frame is None or getattr(frame, "empty", True):
        return []

    events: list[dict] = []
    for index, row in frame.iterrows():
        report_date = _normalise_date(index)
        if report_date is None:
            continue
        events.append(
            {
                "ticker": ticker.upper(),
                "report_date": report_date.isoformat(),
                "report_time": None,
                "eps_estimate": _maybe_float(row.get("EPS Estimate")),
                "eps_actual": _maybe_float(row.get("Reported EPS")),
                "revenue_estimate": None,
                "revenue_actual": None,
            }
        )
    return events


def _normalise_date(value) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        ts = pd.Timestamp(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(ts):
        return None
    return ts.date()


def _maybe_float(value) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result:  # NaN guard
        return None
    return result


def sync_earnings_for_tickers(tickers: Iterable[str], *, force_refresh: bool = False) -> int:
    """Refresh the earnings calendar for the given tickers.

    Returns the number of tickers that were actually re-fetched (others were
    skipped because their cache is still fresh).
    """
    refreshed = 0
    for ticker in tickers:
        ticker = ticker.upper()
        if not force_refresh and _is_cache_fresh(ticker):
            continue
        try:
            events = _fetch_via_yfinance(ticker)
        except EarningsIngestionError:
            continue
        if events:
            upsert_earnings(events)
        refreshed += 1
    return refreshed


def upcoming_earnings(tickers: list[str] | None = None, *, days_ahead: int = 60) -> list[EarningsEvent]:
    """Return earnings events in the next ``days_ahead`` days."""
    if tickers:
        sync_earnings_for_tickers(tickers)
    rows = list_upcoming(tickers, days_ahead=days_ahead)
    out: list[EarningsEvent] = []
    for row in rows:
        try:
            parsed_date = date.fromisoformat(str(row["report_date"])[:10])
        except ValueError:
            continue
        out.append(
            EarningsEvent(
                ticker=str(row["ticker"]).upper(),
                report_date=parsed_date,
                report_time=row.get("report_time"),
                eps_estimate=row.get("eps_estimate"),
                eps_actual=row.get("eps_actual"),
                revenue_estimate=row.get("revenue_estimate"),
                revenue_actual=row.get("revenue_actual"),
            )
        )
    return out


def days_until_next_earnings(ticker: str) -> int | None:
    """How many calendar days until the next earnings event, if known."""
    sync_earnings_for_tickers([ticker])
    next_date = next_earnings_date(ticker)
    if next_date is None:
        return None
    delta = (next_date - date.today()).days
    return delta if delta >= 0 else None


def earnings_guardrail_for_holding(ticker: str, risk_tolerance: str) -> str | None:
    """Produce a guardrail string for a holding with imminent earnings.

    Conservative profiles get warned at <=14 days. Moderate at <=7. Aggressive
    only at <=3 (they can self-select bigger gap exposure).
    """
    days = days_until_next_earnings(ticker)
    if days is None:
        return None
    thresholds = {"low": 14, "medium": 7, "high": 3}
    cutoff = thresholds.get(risk_tolerance.lower(), 7)
    if days <= cutoff:
        return (
            f"{ticker}: earnings en {days} dia(s). Gap risk puede borrar la tesis tecnica. "
            f"Reduci size o esperar al post-report."
        )
    return None
