from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol

import pandas as pd

from ..config import HORIZON_CONFIG
from ..contracts import Horizon
from ..utils import TTLCache

logger = logging.getLogger("market_bot.api")


class MarketDataError(RuntimeError):
    """Raised when a provider cannot deliver usable market data."""


@dataclass
class PriceHistory:
    ticker: str
    horizon: Horizon
    interval: str
    period: str
    frame: pd.DataFrame


@dataclass
class InstrumentContext:
    ticker: str
    display_name: str
    sector: str | None = None
    industry: str | None = None
    currency: str | None = None
    earnings_date: str | None = None


class MarketDataAdapter(Protocol):
    def get_price_history(self, ticker: str, horizon: Horizon) -> PriceHistory:
        ...

    def get_instrument_context(self, ticker: str) -> InstrumentContext:
        ...


class YFinanceMarketDataAdapter:
    def __init__(self):
        self._price_cache: TTLCache[PriceHistory] = TTLCache(ttl_seconds=300)
        self._context_cache: TTLCache[InstrumentContext] = TTLCache(ttl_seconds=3600)

    def _load_yfinance(self):
        try:
            import yfinance as yf
        except ModuleNotFoundError as exc:
            raise MarketDataError(
                "yfinance no esta instalado. Instala dependencias antes de usar el adapter."
            ) from exc
        return yf

    def get_price_history(self, ticker: str, horizon: Horizon) -> PriceHistory:
        cache_key = (ticker.upper(), horizon.value)
        cached = self._price_cache.get(cache_key)
        if cached is not None:
            return cached

        yf = self._load_yfinance()
        config = HORIZON_CONFIG[horizon]
        frame = yf.download(
            ticker,
            period=config.period,
            interval=config.interval,
            auto_adjust=True,
            progress=False,
        )
        if frame.empty:
            raise MarketDataError(f"No se encontraron precios para {ticker}.")

        if isinstance(frame.columns, pd.MultiIndex):
            frame.columns = frame.columns.get_level_values(0)

        frame = frame.rename(columns={column: str(column).title() for column in frame.columns})
        frame.columns.name = None
        frame = frame.loc[:, ~frame.columns.duplicated(keep="first")]
        required_columns = ["Open", "High", "Low", "Close", "Volume"]
        missing_columns = [column for column in required_columns if column not in frame.columns]
        if missing_columns:
            raise MarketDataError(
                f"Datos incompletos para {ticker}. Faltan columnas: {missing_columns}."
            )

        frame = frame.loc[:, required_columns].apply(pd.to_numeric, errors="coerce").dropna().sort_index()
        if len(frame) < config.warmup_bars:
            raise MarketDataError(
                f"Historial insuficiente para {ticker} en horizonte {horizon.value}."
            )

        history = PriceHistory(
            ticker=ticker,
            horizon=horizon,
            interval=config.interval,
            period=config.period,
            frame=frame,
        )
        return self._price_cache.set(cache_key, history)

    def prefetch_universe(self, tickers: list[str], horizon: Horizon) -> None:
        """Warm ``self._price_cache`` with a single batched yfinance call.

        One ``yf.download`` for the whole universe replaces N sequential
        per-ticker fetches inside the ranking thread pool. Each surviving
        ticker is normalised into the same :class:`PriceHistory` shape that
        ``get_price_history`` produces, so the downstream code path is
        unchanged.

        Failures (network outage, yfinance hiccup, missing tickers) are
        silently dropped — ``get_price_history`` will fall back to its own
        per-symbol fetch for cache misses.
        """
        normalized = sorted({t.upper() for t in tickers if t})
        targets = [
            t for t in normalized
            if self._price_cache.get((t, horizon.value)) is None
        ]
        if not targets:
            return

        try:
            yf = self._load_yfinance()
        except MarketDataError:
            return

        config = HORIZON_CONFIG[horizon]
        started = time.perf_counter()
        try:
            frame = yf.download(
                targets,
                period=config.period,
                interval=config.interval,
                auto_adjust=True,
                group_by="ticker",
                progress=False,
                threads=True,
            )
        except Exception:
            return

        hits = 0
        if frame is None or getattr(frame, "empty", True):
            self._log_batch(len(targets), 0, started)
            return

        required_columns = ["Open", "High", "Low", "Close", "Volume"]

        def _store(symbol: str, sub: pd.DataFrame) -> bool:
            if sub is None or sub.empty:
                return False
            sub = sub.copy()
            if isinstance(sub.columns, pd.MultiIndex):
                sub.columns = sub.columns.get_level_values(0)
            sub = sub.rename(columns={c: str(c).title() for c in sub.columns})
            sub.columns.name = None
            sub = sub.loc[:, ~sub.columns.duplicated(keep="first")]
            missing = [c for c in required_columns if c not in sub.columns]
            if missing:
                return False
            sub = (
                sub.loc[:, required_columns]
                .apply(pd.to_numeric, errors="coerce")
                .dropna()
                .sort_index()
            )
            if len(sub) < config.warmup_bars:
                return False
            history = PriceHistory(
                ticker=symbol,
                horizon=horizon,
                interval=config.interval,
                period=config.period,
                frame=sub,
            )
            self._price_cache.set((symbol, horizon.value), history)
            return True

        if isinstance(frame.columns, pd.MultiIndex):
            top_level = set(frame.columns.get_level_values(0))
            for symbol in targets:
                if symbol not in top_level:
                    continue
                try:
                    sub = frame[symbol]
                except KeyError:
                    continue
                if _store(symbol, sub):
                    hits += 1
        else:
            if len(targets) == 1 and _store(targets[0], frame):
                hits += 1

        self._log_batch(len(targets), hits, started)

    def _log_batch(self, total: int, hits: int, started: float) -> None:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        try:
            logger.info(
                "yfinance batch fetch",
                extra={
                    "symbols": total,
                    "elapsed_ms": elapsed_ms,
                    "hit_rate": round(hits / total, 3) if total else 0.0,
                },
            )
        except Exception:
            pass

    def get_instrument_context(self, ticker: str) -> InstrumentContext:
        cache_key = ticker.upper()
        cached = self._context_cache.get(cache_key)
        if cached is not None:
            return cached

        yf = self._load_yfinance()
        instrument = yf.Ticker(ticker)

        try:
            info = instrument.info or {}
        except Exception:
            info = {}

        context = InstrumentContext(
            ticker=ticker,
            display_name=info.get("shortName") or info.get("longName") or ticker,
            sector=info.get("sector"),
            industry=info.get("industry"),
            currency=info.get("currency"),
            earnings_date=self._extract_earnings_date(instrument),
        )
        return self._context_cache.set(cache_key, context)

    def _extract_earnings_date(self, instrument: Any) -> str | None:
        try:
            calendar = instrument.calendar
        except Exception:
            return None

        if isinstance(calendar, pd.DataFrame) and not calendar.empty:
            for key in ("Earnings Date", "Ex-Dividend Date"):
                if key in calendar.index:
                    return self._normalize_date_value(calendar.loc[key].iloc[0])

        if isinstance(calendar, dict):
            for key in ("Earnings Date", "Ex-Dividend Date"):
                if key in calendar:
                    return self._normalize_date_value(calendar[key])

        return None

    def _normalize_date_value(self, raw_value: Any) -> str | None:
        if raw_value is None:
            return None
        if isinstance(raw_value, (list, tuple)) and raw_value:
            raw_value = raw_value[0]
        if isinstance(raw_value, pd.Timestamp):
            return raw_value.date().isoformat()
        if isinstance(raw_value, datetime):
            return raw_value.date().isoformat()
        if isinstance(raw_value, date):
            return raw_value.isoformat()
        return str(raw_value)
