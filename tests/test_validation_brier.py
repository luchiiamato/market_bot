"""Brier score + reliability bins — pure-numerical tests, no IO."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from market_bot.validation import (
    brier_score,
    reliability_bins,
    walk_forward_predictions,
)


def test_brier_perfect_predictions_is_zero():
    assert brier_score([1.0, 0.0, 1.0], [1, 0, 1]) == 0.0


def test_brier_worst_predictions_is_one():
    assert brier_score([1.0, 0.0], [0, 1]) == 1.0


def test_brier_always_fifty_fifty_is_quarter():
    assert brier_score([0.5, 0.5, 0.5, 0.5], [0, 1, 1, 0]) == 0.25


def test_brier_clips_out_of_range_predictions():
    # 1.5 should clip to 1.0 (correct against label=1).
    assert brier_score([1.5], [1]) == 0.0
    # -0.2 should clip to 0.0 (correct against label=0).
    assert brier_score([-0.2], [0]) == 0.0


def test_brier_empty_input_returns_zero():
    assert brier_score([], []) == 0.0


def test_brier_mismatched_lengths_raises():
    with pytest.raises(ValueError):
        brier_score([0.5], [1, 0])


def test_reliability_bins_count_matches_argument():
    bins = reliability_bins([0.1, 0.5, 0.9], [0, 1, 1], num_bins=5)
    assert len(bins) == 5


def test_reliability_bin_aggregates_fraction_positive():
    predictions = [0.05, 0.06, 0.07]
    labels = [1, 0, 1]
    bins = reliability_bins(predictions, labels, num_bins=10)
    # All three predictions fall in the first bin [0, 0.1).
    first = bins[0]
    assert first.sample_size == 3
    assert math.isclose(first.fraction_positive, 2 / 3, abs_tol=0.01)


def test_reliability_last_bin_includes_one():
    # Without inclusive-right on the last bin, prediction=1.0 would fall
    # into no bucket and the calibration view would silently lose data.
    bins = reliability_bins([1.0], [1], num_bins=10)
    assert bins[-1].sample_size == 1


def test_walk_forward_pairs_predictions_with_future_labels():
    closes = list(range(100, 200))  # strictly increasing
    frame = pd.DataFrame({"Close": closes})

    # Predictor always says 0.8 — and since the series is monotonically
    # rising, every label should be 1.
    predictions, labels = walk_forward_predictions(
        frame,
        lambda _slice: 0.8,
        warmup=10,
        horizon_days=3,
        step_days=1,
    )
    assert len(predictions) == len(labels)
    assert len(predictions) > 0
    assert all(p == 0.8 for p in predictions)
    assert all(label == 1 for label in labels)


def test_walk_forward_skips_predictor_exceptions():
    frame = pd.DataFrame({"Close": list(range(50, 150))})
    call_count = {"n": 0}

    def flaky_predictor(_slice):
        call_count["n"] += 1
        if call_count["n"] % 2 == 0:
            raise RuntimeError("boom")
        return 0.6

    predictions, _labels = walk_forward_predictions(
        frame, flaky_predictor, warmup=10, horizon_days=2, step_days=1
    )
    # Roughly half the calls should have survived.
    assert 0 < len(predictions) < call_count["n"]


def test_walk_forward_returns_empty_when_history_too_short():
    frame = pd.DataFrame({"Close": [10, 11, 12]})
    predictions, labels = walk_forward_predictions(
        frame, lambda _slice: 0.5, warmup=60, horizon_days=5
    )
    assert predictions == [] and labels == []
