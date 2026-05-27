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
    "AAPL",
    "ABBV",
    "ABEV",
    "AMZN",
    "AMD",
    "BABA",
    "BAC",
    "BRK.B",
    "COIN",
    "DIS",
    "GGAL",
    "GOOGL",
    "IBB",
    "INTC",
    "JPM",
    "KO",
    "LLY",
    "MCD",
    "MELI",
    "META",
    "MSFT",
    "NVDA",
    "PAM",
    "PBR",
    "PLTR",
    "QQQ",
    "SHOP",
    "SNOW",
    "SPOT",
    "SPY",
    "TSLA",
    "TSM",
    "UBER",
    "VALE",
    "VIST",
    "WMT",
    "XOM",
    "YPF",
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


SUGGESTION_UNIVERSE = [
    "AAPL",
    "AMZN",
    "GGAL",
    "GOOGL",
    "JPM",
    "MELI",
    "META",
    "MSFT",
    "NVDA",
    "PLTR",
    "QQQ",
    "SPY",
    "TSLA",
    "YPF",
]


def is_cedear_ticker(ticker: str) -> bool:
    return ticker.upper() in CEDEAR_UNIVERSE
