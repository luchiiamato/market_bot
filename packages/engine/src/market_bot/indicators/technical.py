from __future__ import annotations

import numpy as np
import pandas as pd

from ..contracts import IndicatorSnapshot


def compute_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    close = data["Close"]
    high = data["High"]
    low = data["Low"]
    volume = data["Volume"]

    data["sma_20"] = close.rolling(window=20).mean()
    data["sma_50"] = close.rolling(window=50).mean()
    data["sma_200"] = close.rolling(window=200).mean()

    for span in (9, 20, 50, 200):
        data[f"ema_{span}"] = close.ewm(span=span, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    data["rsi"] = (100 - (100 / (1 + rs))).fillna(50.0)

    data["macd"] = close.ewm(span=12, adjust=False).mean() - close.ewm(
        span=26, adjust=False
    ).mean()
    data["macd_signal"] = data["macd"].ewm(span=9, adjust=False).mean()

    data["bb_middle"] = data["sma_20"]
    rolling_std = close.rolling(window=20).std()
    data["bb_upper"] = data["bb_middle"] + (rolling_std * 2)
    data["bb_lower"] = data["bb_middle"] - (rolling_std * 2)

    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    data["atr"] = true_range.rolling(window=14).mean()

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=data.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=data.index,
    )
    atr_smooth = true_range.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean() / atr_smooth
    minus_di = (
        100 * minus_dm.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean() / atr_smooth
    )
    directional_sum = (plus_di + minus_di).replace(0.0, np.nan)
    dx = (100 * (plus_di - minus_di).abs() / directional_sum).fillna(0.0)
    data["adx"] = dx.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()

    highest_high = high.rolling(window=14).max()
    lowest_low = low.rolling(window=14).min()
    denominator = (highest_high - lowest_low).replace(0.0, np.nan)
    data["stoch_k"] = ((close - lowest_low) / denominator * 100).fillna(50.0)
    data["stoch_d"] = data["stoch_k"].rolling(window=3).mean().fillna(50.0)

    data["momentum_10"] = close.diff(periods=10)
    data["volume_ratio"] = volume / volume.rolling(window=20).mean().replace(0.0, np.nan)
    data["support_20"] = low.rolling(window=20).min()
    data["resistance_20"] = high.rolling(window=20).max()
    data["price_vs_sma50_pct"] = ((close - data["sma_50"]) / data["sma_50"]) * 100

    return data.dropna()


def build_indicator_snapshot(data: pd.DataFrame) -> IndicatorSnapshot:
    latest = data.iloc[-1]
    return IndicatorSnapshot(
        price=float(latest["Close"]),
        rsi=float(latest["rsi"]),
        macd=float(latest["macd"]),
        macd_signal=float(latest["macd_signal"]),
        adx=float(latest["adx"]),
        atr=float(latest["atr"]),
        volume_ratio=float(latest["volume_ratio"]),
        sma_20=float(latest["sma_20"]),
        sma_50=float(latest["sma_50"]),
        sma_200=float(latest["sma_200"]),
        bb_upper=float(latest["bb_upper"]),
        bb_lower=float(latest["bb_lower"]),
        support=float(latest["support_20"]),
        resistance=float(latest["resistance_20"]),
    )
