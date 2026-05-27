from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import requests

from market_bot.utils import TTLCache


class ArgentinaBenchmarkError(RuntimeError):
    """Raised when benchmark providers cannot deliver data."""


@dataclass
class ExchangeRates:
    as_of: date
    official: float
    mep: float
    ccl: float
    source: str


@dataclass
class PeriodBenchmarkSnapshot:
    start_date: date
    end_date: date
    purchase_exchange: ExchangeRates
    current_exchange: ExchangeRates
    inflation_factor: float
    fixed_term_factor: float
    inflation_source: str
    rates_source: str
    fixed_term_source: str


class ArgentinaBenchmarkService:
    SERIES_URLS = {
        "official": "https://api.argentinadatos.com/v1/cotizaciones/dolares/oficial",
        "mep": "https://api.argentinadatos.com/v1/cotizaciones/dolares/bolsa",
        "ccl": "https://api.argentinadatos.com/v1/cotizaciones/dolares/contadoconliqui",
        "inflation": "https://api.argentinadatos.com/v1/finanzas/indices/inflacion",
        "fixed_term": "https://api.argentinadatos.com/v1/finanzas/tasas/depositos30Dias",
    }

    def __init__(self) -> None:
        self._series_cache: TTLCache[list[dict]] = TTLCache(ttl_seconds=21_600)

    def get_current_exchange_rates(self) -> ExchangeRates:
        today = date.today()
        return ExchangeRates(
            as_of=today,
            official=self.get_exchange_rate("official", today),
            mep=self.get_exchange_rate("mep", today),
            ccl=self.get_exchange_rate("ccl", today),
            source="api.argentinadatos.com",
        )

    def get_exchange_rate(self, house: str, target_date: date) -> float:
        series = self._load_series(house)
        series_dates = [self._parse_date(item["fecha"]) for item in series]
        index = bisect_right(series_dates, target_date) - 1
        if index < 0:
            raise ArgentinaBenchmarkError(
                f"No hay cotizacion historica disponible para {house} en {target_date.isoformat()}."
            )
        item = series[index]
        return float(item.get("venta") or item.get("compra") or 0.0)

    def get_inflation_factor(self, start_date: date, end_date: date) -> float:
        if end_date <= start_date:
            return 1.0
        series = self._load_series("inflation")
        factor = 1.0
        for item in series:
            item_date = self._parse_date(item["fecha"])
            if item_date <= start_date or item_date > end_date:
                continue
            factor *= 1 + (float(item["valor"]) / 100.0)
        return factor

    def get_fixed_term_factor(self, start_date: date, end_date: date) -> float:
        if end_date <= start_date:
            return 1.0
        series = self._load_series("fixed_term")
        dated_series = [
            (self._parse_date(item["fecha"]), float(item["valor"]))
            for item in series
        ]
        series_dates = [item[0] for item in dated_series]
        index = bisect_right(series_dates, start_date) - 1
        if index < 0:
            raise ArgentinaBenchmarkError(
                f"No hay tasa historica de plazo fijo disponible para {start_date.isoformat()}."
            )

        current_date = start_date
        current_rate = dated_series[index][1]
        factor = 1.0
        next_index = index + 1

        while current_date < end_date:
            next_change_date = end_date
            if next_index < len(dated_series):
                next_change_date = min(end_date, dated_series[next_index][0])
            days = (next_change_date - current_date).days
            if days > 0:
                factor *= (1 + ((current_rate / 100.0) / 365.0)) ** days
            current_date = next_change_date
            if next_index < len(dated_series) and current_date == dated_series[next_index][0]:
                current_rate = dated_series[next_index][1]
                next_index += 1

        return factor

    def build_period_snapshot(self, start_date: date, end_date: date) -> PeriodBenchmarkSnapshot:
        purchase_exchange = ExchangeRates(
            as_of=start_date,
            official=self.get_exchange_rate("official", start_date),
            mep=self.get_exchange_rate("mep", start_date),
            ccl=self.get_exchange_rate("ccl", start_date),
            source="api.argentinadatos.com",
        )
        current_exchange = ExchangeRates(
            as_of=end_date,
            official=self.get_exchange_rate("official", end_date),
            mep=self.get_exchange_rate("mep", end_date),
            ccl=self.get_exchange_rate("ccl", end_date),
            source="api.argentinadatos.com",
        )
        return PeriodBenchmarkSnapshot(
            start_date=start_date,
            end_date=end_date,
            purchase_exchange=purchase_exchange,
            current_exchange=current_exchange,
            inflation_factor=self.get_inflation_factor(start_date, end_date),
            fixed_term_factor=self.get_fixed_term_factor(start_date, end_date),
            inflation_source="api.argentinadatos.com",
            rates_source="api.argentinadatos.com",
            fixed_term_source="api.argentinadatos.com",
        )

    def _load_series(self, key: str) -> list[dict]:
        cached = self._series_cache.get(key)
        if cached is not None:
            return cached

        try:
            response = requests.get(self.SERIES_URLS[key], timeout=20)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise ArgentinaBenchmarkError(f"No se pudo cargar la serie {key}.") from exc

        if not isinstance(payload, list) or not payload:
            raise ArgentinaBenchmarkError(f"La serie {key} vino vacia o invalida.")
        return self._series_cache.set(key, payload)

    def _parse_date(self, raw_value: str) -> date:
        return datetime.fromisoformat(raw_value[:10]).date()
