from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol

import pandas as pd

from ..config import HORIZON_CONFIG
from ..contracts import Horizon
from ..utils import TTLCache


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
