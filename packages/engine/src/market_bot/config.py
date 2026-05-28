from __future__ import annotations

from dataclasses import dataclass

from .contracts import Horizon


@dataclass(frozen=True)
class HorizonConfig:
    period: str
    interval: str
    warmup_bars: int


HORIZON_CONFIG = {
    Horizon.SHORT: HorizonConfig(period="180d", interval="1h", warmup_bars=220),
    Horizon.LONG: HorizonConfig(period="5y", interval="1d", warmup_bars=260),
}


CEDEAR_UNIVERSE = [
    # Mega-caps / index
    "AAPL", "AMZN", "GOOGL", "META", "MSFT", "NVDA", "TSLA", "QQQ", "SPY",
    # Argentina ADRs (locales fuertes)
    "GGAL", "MELI", "PAM", "PBR", "VIST", "YPF",
    # Semis / hardware
    "AMD", "AVGO", "INTC", "TSM", "ARM", "MU", "QCOM",
    # AI / cloud / data infra (los "raros calientes" pedidos)
    "SNOW", "PLTR", "CRWD", "DDOG", "NET", "MDB", "ZS", "OKTA", "CRM", "ORCL", "ADBE",
    # Fintech / consumer tech
    "COIN", "PYPL", "SHOP", "SQ", "ABNB", "UBER", "SPOT",
    # Healthcare / pharma
    "ABBV", "LLY", "UNH",
    # Financials
    "JPM", "BAC", "BRK.B",
    # Consumer staples / discretionary
    "KO", "MCD", "WMT", "DIS",
    # Energy / materials
    "XOM", "VALE",
    # EM / China
    "BABA", "BIDU", "JD", "PDD", "NU",
    # ETFs / sector
    "IBB",
    # Brasil
    "ABEV",
    # Astera Labs (AI chip interconnect, listed BYMA 2025)
    "ALAB",
]


DEFAULT_UNIVERSE = [
    "AAPL",
    "PLTR",
    "QQQ",
    "SPY",
    "TSLA",
    "NVDA",
    "MELI",
    "YPF",
]


# Universo usado por el ranking cuando el cliente no pasa lista explícita y
# pide cedear_only. Ahora arranca igual a CEDEAR_UNIVERSE — que el motor
# decida qué subir y qué bajar, no la lista. Antes había 14 mega-caps fijos
# y por eso SNOW (y similares) nunca aparecían aunque tuvieran catalysts.
SUGGESTION_UNIVERSE = list(CEDEAR_UNIVERSE)


def is_cedear_ticker(ticker: str) -> bool:
    return ticker.upper() in CEDEAR_UNIVERSE
