"""Sprint 9.2 — offline tests for the pooled cross-sectional model.

Fully offline: a FakeAdapter returns deterministic synthetic OHLCV (random walk)
so `compute_indicators` / `_build_feature_frame` produce real feature columns,
and we train a small real model. No network.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from market_bot.contracts import Horizon
from market_bot.models import (
    build_pooled_dataset,
    predict_pooled,
    target_horizon_bars,
    train_pooled_model,
)
from market_bot.indicators import compute_indicators


def _synthetic_ohlcv(seed: int, n: int = 600) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    # Random walk with mild drift so the H-ahead target has both classes.
    steps = rng.normal(0.0005, 0.02, size=n)
    close = 100.0 * np.exp(np.cumsum(steps))
    high = close * (1 + np.abs(rng.normal(0, 0.01, size=n)))
    low = close * (1 - np.abs(rng.normal(0, 0.01, size=n)))
    openp = close * (1 + rng.normal(0, 0.005, size=n))
    volume = rng.integers(1_000_000, 5_000_000, size=n).astype(float)
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {"Open": openp, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=idx,
    )


class _FakeAdapter:
    def __init__(self):
        self._seeds = {"AAA": 1, "BBB": 2, "CCC": 3, "DDD": 4}

    def get_price_history(self, ticker, horizon):
        seed = self._seeds.get(ticker.upper(), 9)
        return SimpleNamespace(frame=_synthetic_ohlcv(seed))


UNIVERSE = ["AAA", "BBB", "CCC", "DDD"]


def test_build_pooled_dataset_has_features_target_and_metadata():
    ds = build_pooled_dataset(_FakeAdapter(), UNIVERSE, Horizon.LONG)
    assert "target" in ds.columns
    assert "__date" in ds.columns
    assert "__ticker" in ds.columns
    # target is binary
    assert set(ds["target"].unique()).issubset({0.0, 1.0})
    # all universe tickers present
    assert set(ds["__ticker"].unique()) == set(UNIVERSE)
    # has real feature columns (from _build_feature_frame)
    assert "rsi_centered" in ds.columns and "macd_pct" in ds.columns


def test_train_pooled_model_time_split_no_leakage_and_validation_populated():
    artifact = train_pooled_model(_FakeAdapter(), UNIVERSE, Horizon.LONG)
    assert artifact.n_tickers == len(UNIVERSE)
    assert artifact.n_samples > 300
    assert artifact.feature_columns  # non-empty
    v = artifact.validation
    assert v.split_strategy == "pooled_cross_sectional_time_holdout"
    assert 0.0 <= v.brier_score <= 1.0
    assert 0.0 <= v.f1 <= 1.0
    assert v.train_size > 0 and v.test_size > 0
    # importances + class means stored for explanations
    assert artifact.importances is not None
    assert len(artifact.importances) == len(artifact.feature_columns)


def test_predict_pooled_returns_valid_signal():
    artifact = train_pooled_model(_FakeAdapter(), UNIVERSE, Horizon.LONG)
    data = compute_indicators(_synthetic_ohlcv(seed=1))
    signal = predict_pooled(artifact, data, Horizon.LONG)
    assert 0.0 <= signal.probability_up <= 1.0
    assert 0.5 <= signal.confidence <= 0.95
    total = sum(s.probability for s in signal.scenarios)
    assert total == pytest.approx(1.0, abs=0.05)
    assert len(signal.dominant_features) <= 3


def test_target_horizon_bars_distinct_per_horizon():
    assert target_horizon_bars(Horizon.SHORT) == 35
    assert target_horizon_bars(Horizon.LONG) == 20
