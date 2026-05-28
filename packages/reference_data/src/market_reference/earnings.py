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

# Historical surprise grid cache. yfinance's earnings_history can be slow and is
# rate-limited; we keep an in-memory TTL cache (24h) keyed by upper-cased ticker.
# This is intentionally separate from the upcoming-events store so that the two
# never cross-pollute (one is historical and immutable; the other shifts daily).
_HISTORY_CACHE: dict[str, tuple[float, list[dict]]] = {}
_HISTORY_CACHE_TTL_SECONDS = 24 * 60 * 60

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


def _fiscal_quarter_label(report_dt: date) -> str:
    """Best-effort fiscal quarter label like ``"Q1 FY26"``.

    yfinance does not expose the issuer's fiscal calendar reliably, so we fall
    back to calendar quarter mapped to fiscal year = report year + 1 when the
    report is in Nov/Dec (a common convention for issuers with Jan/Feb fiscal
    year-ends such as SNOW, CRM, NVDA). Anything else uses the calendar year.
    Good enough for an at-a-glance grid — accuracy is "the quarter and the
    year", not "the issuer's exact reporting label".
    """
    month = report_dt.month
    if month in (1, 2, 3):
        quarter = 4  # typically the prior fiscal year's Q4 report
        fiscal_year = report_dt.year
    elif month in (4, 5, 6):
        quarter = 1
        fiscal_year = report_dt.year + 1
    elif month in (7, 8, 9):
        quarter = 2
        fiscal_year = report_dt.year + 1
    else:
        quarter = 3
        fiscal_year = report_dt.year + 1
    return f"Q{quarter} FY{str(fiscal_year)[-2:]}"


def _next_trading_day_return(ticker: str, report_dt: date) -> tuple[float | None, date | None]:
    """Return (next_day_close_pct_change, next_day_close_date) for ``report_dt``.

    Pulls a 10-day window around the report so we can compute close-to-close
    return for the first session AFTER the print. If yfinance has no data
    (delisted, weekend reports, very recent IPO), returns ``(None, None)``.
    """
    try:
        import yfinance as yf
    except ModuleNotFoundError:  # pragma: no cover
        return (None, None)

    start = report_dt - timedelta(days=2)
    end = report_dt + timedelta(days=10)
    try:
        frame = yf.Ticker(ticker).history(start=start.isoformat(), end=end.isoformat(), auto_adjust=False)
    except Exception:  # pragma: no cover
        return (None, None)

    if frame is None or getattr(frame, "empty", True):
        return (None, None)

    closes: list[tuple[date, float]] = []
    for idx, row in frame.iterrows():
        try:
            ts = pd.Timestamp(idx)
        except (TypeError, ValueError):
            continue
        if pd.isna(ts):
            continue
        close_val = _maybe_float(row.get("Close"))
        if close_val is None:
            continue
        closes.append((ts.date(), close_val))

    if len(closes) < 2:
        return (None, None)

    closes.sort(key=lambda item: item[0])

    # Find the report-day close (or the most recent trading day before it) and
    # the very next session's close.
    report_idx: int | None = None
    for i, (close_date, _) in enumerate(closes):
        if close_date <= report_dt:
            report_idx = i
        else:
            break
    if report_idx is None or report_idx + 1 >= len(closes):
        return (None, None)

    _, report_close = closes[report_idx]
    next_date, next_close = closes[report_idx + 1]
    if report_close == 0:
        return (None, None)
    pct = (next_close - report_close) / report_close
    return (pct, next_date)


def _fetch_history_via_yfinance(ticker: str, limit: int) -> list[dict]:
    """Pull historical earnings surprises from yfinance.

    Defensive: yfinance occasionally returns ``None``, an empty frame, or rows
    with NaN actuals (forward quarters that leaked into the history endpoint).
    We drop anything without an actual EPS — those aren't reported yet.
    """
    try:
        import yfinance as yf
    except ModuleNotFoundError:  # pragma: no cover
        return []

    try:
        frame = getattr(yf.Ticker(ticker), "earnings_history", None)
    except Exception:  # pragma: no cover
        return []

    if frame is None or getattr(frame, "empty", True):
        return []

    rows: list[tuple[date, dict]] = []
    for index, row in frame.iterrows():
        report_dt = _normalise_date(index)
        if report_dt is None:
            continue
        eps_actual = _maybe_float(row.get("epsActual"))
        if eps_actual is None:
            # No actuals reported yet — skip future quarters.
            continue
        eps_estimate = _maybe_float(row.get("epsEstimate"))
        surprise_pct_raw = _maybe_float(row.get("surprisePercent"))
        # yfinance returns surprisePercent already as a percent (e.g. 22.2 for
        # +22.2%). We expose a *ratio* (0.222) so the frontend can format it
        # however it wants.
        surprise_pct = surprise_pct_raw / 100.0 if surprise_pct_raw is not None else None
        if surprise_pct is None and eps_estimate not in (None, 0) and eps_actual is not None:
            surprise_pct = (eps_actual - eps_estimate) / abs(eps_estimate)

        beat: bool | None
        if eps_estimate is None or eps_actual is None:
            beat = None
        else:
            beat = eps_actual >= eps_estimate

        next_day_return, next_day_close_date = _next_trading_day_return(ticker, report_dt)

        rows.append(
            (
                report_dt,
                {
                    "fiscal_quarter": _fiscal_quarter_label(report_dt),
                    "report_date": report_dt.isoformat(),
                    "eps_estimate": eps_estimate,
                    "eps_actual": eps_actual,
                    "surprise_pct": surprise_pct,
                    "beat": beat,
                    "next_day_return_pct": next_day_return,
                    "next_day_close_date": next_day_close_date.isoformat() if next_day_close_date else None,
                },
            )
        )

    rows.sort(key=lambda item: item[0], reverse=True)
    return [payload for _, payload in rows[:limit]]


def fetch_earnings_history(ticker: str, limit: int = 12) -> list[dict]:
    """Return the last ``limit`` reported quarters for ``ticker``.

    Result rows are dicts (not dataclasses) so the API layer can validate them
    against a pydantic schema directly. Empty list on any failure — earnings
    history is a nice-to-have surface, never block the rest of the panel.

    Caching: keyed by ``(TICKER, limit)`` with a 24h TTL. yfinance's response
    is stable across a trading day and rate-limits aggressively if hit hard.
    """
    if not ticker:
        return []
    normalized = ticker.upper()
    cache_key = f"{normalized}:{limit}"
    now = datetime.utcnow().timestamp()
    cached = _HISTORY_CACHE.get(cache_key)
    if cached is not None:
        cached_at, payload = cached
        if now - cached_at < _HISTORY_CACHE_TTL_SECONDS:
            return payload

    try:
        rows = _fetch_history_via_yfinance(normalized, limit)
    except Exception:  # pragma: no cover — defensive: never bubble up
        rows = []

    _HISTORY_CACHE[cache_key] = (now, rows)
    return rows


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
