"""Walk-forward ranking backtest.

Tests whether the engine's technical signals have predictive edge by
simulating a weekly-rebalanced long-top-3 strategy over a historical window
and comparing it against SPY buy-and-hold and plazo fijo.

Signal used: composite of RSI(14) + 20-day momentum (deterministic, fast,
no ML retraining). This mirrors the deterministic component of ``rank_score``
and avoids the lookahead bias that per-ticker ML models introduce when
re-applied to historical data.

Designed to run in ~5-15s for 57 tickers over 90 days.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any


@dataclass
class PeriodResult:
    anchor_date: str          # ISO date string
    top_tickers: list[str]
    strategy_return: float    # actual return of the top-n basket that period
    spy_return: float         # SPY return for the same period
    pf_return: float          # plazo fijo equivalent return for the period
    beat_spy: bool


@dataclass
class RankingBacktestResult:
    horizon: str
    lookback_days: int
    top_n: int
    step_days: int
    n_periods: int
    hit_rate_vs_spy: float | None      # fraction of periods where top-n beat SPY
    hit_rate_positive: float | None    # fraction of periods with positive return
    strategy_cum_return: float | None  # compounded return of the strategy
    spy_cum_return: float | None       # compounded return of SPY buy-and-hold
    pf_cum_return: float | None        # plazo fijo compounded return for same window
    avg_period_return: float | None
    sharpe: float | None               # annualized Sharpe (vs 0 risk-free)
    max_drawdown: float | None
    periods: list[PeriodResult] = field(default_factory=list)
    computed_at: str = ""
    error: str | None = None


def _rsi(closes: list[float], period: int = 14) -> float:
    """Return RSI for the last point in ``closes``. Returns 50.0 on error."""
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(0.0, d) for d in deltas[-period:]]
    losses = [max(0.0, -d) for d in deltas[-period:]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1 + rs))


def _momentum(closes: list[float], period: int = 20) -> float:
    """Return price change % over last ``period`` bars. Returns 0.0 on error."""
    if len(closes) < period + 1:
        return 0.0
    base = closes[-period - 1]
    if base <= 0:
        return 0.0
    return (closes[-1] - base) / base


def _rank_signal(closes: list[float]) -> float:
    """Composite signal: 0.6 * (1 - RSI/100) + 0.4 * clamped_momentum.

    Higher = more bullish. RSI component: oversold (low RSI) → higher score.
    Momentum component: normalized to [0, 1] where 0.5 = flat.
    """
    rsi = _rsi(closes)
    mom = _momentum(closes)
    mom_norm = max(0.0, min(1.0, 0.5 + mom * 2.5))  # ±20% maps to ~[0, 1]
    return 0.6 * (1.0 - rsi / 100.0) + 0.4 * mom_norm


def backtest_ranking(
    tickers: list[str],
    *,
    horizon: str = "short",
    lookback_days: int = 90,
    top_n: int = 3,
    step_days: int = 5,
    pf_annual_rate: float = 0.50,  # ARS plazo fijo ~50% annual
) -> RankingBacktestResult:
    """Run the walk-forward ranking backtest.

    Downloads ``lookback_days + horizon_days + 10`` days of daily OHLC for all
    ``tickers`` plus SPY in a single batched yfinance call, then simulates
    weekly rebalancing into the top ``top_n`` tickers by signal.

    ``pf_annual_rate`` is the plazo fijo ARS annual rate used as a benchmark.
    The caller should pass the current rate from ``ArgentinaBenchmarkService``
    for the most accurate comparison.
    """
    from datetime import datetime as _dt

    try:
        import pandas as pd
        import yfinance as yf
    except ModuleNotFoundError as exc:
        return RankingBacktestResult(
            horizon=horizon,
            lookback_days=lookback_days,
            top_n=top_n,
            step_days=step_days,
            n_periods=0,
            hit_rate_vs_spy=None,
            hit_rate_positive=None,
            strategy_cum_return=None,
            spy_cum_return=None,
            pf_cum_return=None,
            avg_period_return=None,
            sharpe=None,
            max_drawdown=None,
            error=str(exc),
        )

    horizon_days = 7 if horizon == "short" else 30
    pf_period_rate = (1 + pf_annual_rate) ** (horizon_days / 365) - 1

    end_date = date.today()
    start_date = end_date - timedelta(days=lookback_days + horizon_days + 15)

    all_symbols = list({t.upper() for t in tickers} | {"SPY"})

    try:
        raw = yf.download(
            all_symbols,
            start=start_date.isoformat(),
            end=end_date.isoformat(),
            interval="1d",
            auto_adjust=True,
            progress=False,
            group_by="ticker",
        )
    except Exception as exc:
        return RankingBacktestResult(
            horizon=horizon, lookback_days=lookback_days, top_n=top_n, step_days=step_days,
            n_periods=0, hit_rate_vs_spy=None, hit_rate_positive=None,
            strategy_cum_return=None, spy_cum_return=None, pf_cum_return=None,
            avg_period_return=None, sharpe=None, max_drawdown=None, error=str(exc),
        )

    # Extract per-ticker close series into a dict {ticker: pd.Series}
    closes: dict[str, pd.Series] = {}
    if isinstance(raw.columns, pd.MultiIndex):
        for sym in all_symbols:
            try:
                s = raw[sym]["Close"].dropna()
                if len(s) > 20:
                    closes[sym] = s
            except (KeyError, TypeError):
                continue
    else:
        # Single-ticker case (shouldn't happen but be safe)
        if "Close" in raw.columns:
            closes[all_symbols[0]] = raw["Close"].dropna()

    spy_series = closes.get("SPY")
    if spy_series is None or len(spy_series) < 20:
        return RankingBacktestResult(
            horizon=horizon, lookback_days=lookback_days, top_n=top_n, step_days=step_days,
            n_periods=0, hit_rate_vs_spy=None, hit_rate_positive=None,
            strategy_cum_return=None, spy_cum_return=None, pf_cum_return=None,
            avg_period_return=None, sharpe=None, max_drawdown=None,
            error="SPY data unavailable",
        )

    # Build a common date index (intersection of all tickers with enough data)
    available = [sym for sym in closes if sym != "SPY" and len(closes[sym]) >= 30]
    if len(available) < 3:
        return RankingBacktestResult(
            horizon=horizon, lookback_days=lookback_days, top_n=top_n, step_days=step_days,
            n_periods=0, hit_rate_vs_spy=None, hit_rate_positive=None,
            strategy_cum_return=None, spy_cum_return=None, pf_cum_return=None,
            avg_period_return=None, sharpe=None, max_drawdown=None,
            error="Not enough ticker data",
        )

    # Use SPY's index as the reference timeline
    common_dates = spy_series.index
    min_warmup = 25  # need at least 25 days of history for RSI(14) + momentum(20)

    period_results: list[PeriodResult] = []
    strategy_equity = [1.0]

    # Walk forward: step every step_days, signal computed at anchor,
    # return measured from anchor to anchor+horizon_days.
    i = min_warmup
    while i + horizon_days < len(common_dates):
        anchor_date = common_dates[i]

        # Score each ticker using data up to and including anchor_date
        scores: dict[str, float] = {}
        for sym in available:
            series = closes[sym]
            hist = series[series.index <= anchor_date]
            if len(hist) < 22:
                continue
            c = hist.values.tolist()
            scores[sym] = _rank_signal(c)

        if len(scores) < top_n:
            i += step_days
            continue

        ranked = sorted(scores, key=scores.__getitem__, reverse=True)
        top_tickers = ranked[:top_n]

        # Compute actual return of top-n basket from anchor to anchor+horizon_days
        future_idx = min(i + horizon_days, len(common_dates) - 1)
        future_date = common_dates[future_idx]

        basket_return = 0.0
        valid = 0
        for sym in top_tickers:
            series = closes[sym]
            p0_s = series[series.index <= anchor_date]
            p1_s = series[series.index <= future_date]
            if p0_s.empty or p1_s.empty:
                continue
            p0 = float(p0_s.iloc[-1])
            p1 = float(p1_s.iloc[-1])
            if p0 > 0:
                basket_return += (p1 - p0) / p0
                valid += 1
        if valid > 0:
            basket_return /= valid
        else:
            i += step_days
            continue

        # SPY return for same period
        spy_p0_s = spy_series[spy_series.index <= anchor_date]
        spy_p1_s = spy_series[spy_series.index <= future_date]
        if spy_p0_s.empty or spy_p1_s.empty:
            i += step_days
            continue
        spy_p0 = float(spy_p0_s.iloc[-1])
        spy_p1 = float(spy_p1_s.iloc[-1])
        spy_ret = (spy_p1 - spy_p0) / spy_p0 if spy_p0 > 0 else 0.0

        period_results.append(PeriodResult(
            anchor_date=str(anchor_date.date()) if hasattr(anchor_date, "date") else str(anchor_date),
            top_tickers=top_tickers,
            strategy_return=round(basket_return, 4),
            spy_return=round(spy_ret, 4),
            pf_return=round(pf_period_rate, 4),
            beat_spy=basket_return > spy_ret,
        ))
        strategy_equity.append(strategy_equity[-1] * (1 + basket_return))

        i += step_days

    if not period_results:
        return RankingBacktestResult(
            horizon=horizon, lookback_days=lookback_days, top_n=top_n, step_days=step_days,
            n_periods=0, hit_rate_vs_spy=None, hit_rate_positive=None,
            strategy_cum_return=None, spy_cum_return=None, pf_cum_return=None,
            avg_period_return=None, sharpe=None, max_drawdown=None,
            error="No periods computed",
        )

    # Aggregate metrics
    n = len(period_results)
    rets = [p.strategy_return for p in period_results]
    hits_spy = sum(1 for p in period_results if p.beat_spy)
    hits_pos = sum(1 for r in rets if r > 0)
    avg_ret = sum(rets) / n

    sharpe: float | None = None
    if n >= 3:
        var = sum((r - avg_ret) ** 2 for r in rets) / (n - 1)
        std = math.sqrt(var) if var > 0 else 0.0
        if std > 0:
            periods_per_year = 252 / step_days
            sharpe = round((avg_ret / std) * math.sqrt(periods_per_year), 3)

    # SPY cumulative return for full window
    spy_first = spy_series[spy_series.index <= pd.Timestamp(period_results[0].anchor_date)]
    spy_last = spy_series[spy_series.index <= pd.Timestamp(period_results[-1].anchor_date)]
    spy_cum = None
    if not spy_first.empty and not spy_last.empty:
        s0 = float(spy_first.iloc[-1])
        s1 = float(spy_last.iloc[-1])
        spy_cum = round((s1 - s0) / s0, 4) if s0 > 0 else None

    # Plazo fijo cumulative for full window (compound)
    n_periods_pf = n
    pf_cum = round((1 + pf_period_rate) ** n_periods_pf - 1, 4)

    # Max drawdown of strategy equity curve
    peak = strategy_equity[0]
    max_dd = 0.0
    for eq in strategy_equity:
        peak = max(peak, eq)
        if peak > 0:
            dd = (peak - eq) / peak
            max_dd = max(max_dd, dd)

    strategy_cum = round(strategy_equity[-1] - 1.0, 4)

    return RankingBacktestResult(
        horizon=horizon,
        lookback_days=lookback_days,
        top_n=top_n,
        step_days=step_days,
        n_periods=n,
        hit_rate_vs_spy=round(hits_spy / n, 3),
        hit_rate_positive=round(hits_pos / n, 3),
        strategy_cum_return=strategy_cum,
        spy_cum_return=spy_cum,
        pf_cum_return=pf_cum,
        avg_period_return=round(avg_ret, 4),
        sharpe=sharpe,
        max_drawdown=round(max_dd, 4),
        periods=period_results,
        computed_at=_dt.utcnow().isoformat(),
    )
