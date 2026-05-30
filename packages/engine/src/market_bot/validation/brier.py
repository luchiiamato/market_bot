"""Walk-forward calibration metrics for the probabilistic signal.

The pipeline:

1. Take a price history of length ``N``.
2. For each anchor day ``t`` (skipping the warm-up window the model needs),
   compute the probabilistic signal as if it were ``t`` (i.e. ignoring data
   from ``t+1`` onwards).
3. Look at the realised return between ``t`` and ``t + horizon_days``. Label
   ``1`` if the return is positive, ``0`` otherwise.
4. Aggregate predictions vs labels into Brier score + reliability bins.

Numerical-only module — no I/O, no logging. Keep it boring so it stays
testable. The orchestration (how to actually get the price history, how to
run the engine on a slice) lives in :mod:`market_bot.service`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReliabilityBin:
    """A single bucket in the reliability diagram."""

    bin_lower: float       # inclusive
    bin_upper: float       # exclusive (except for the last bin)
    sample_size: int
    mean_predicted: float  # average of the predicted probabilities in this bin
    fraction_positive: float  # fraction of samples that actually went up


@dataclass
class BrierResult:
    """Aggregate calibration metrics for a single ticker / window."""

    sample_size: int
    brier_score: float
    reliability_bins: list[ReliabilityBin]


def brier_score(predictions: list[float], labels: list[int]) -> float:
    """Compute the Brier score.

    ``predictions`` are probabilities in ``[0, 1]``.
    ``labels`` are 0/1 outcomes.

    Returns ``0.0`` for an empty input — caller decides whether that's
    meaningful (typically: don't surface it as a real measurement).
    """
    if not predictions:
        return 0.0
    if len(predictions) != len(labels):
        raise ValueError("predictions and labels must have the same length")
    total = 0.0
    for prediction, label in zip(predictions, labels):
        clipped = max(0.0, min(1.0, float(prediction)))
        total += (clipped - float(label)) ** 2
    return round(total / len(predictions), 4)


def reliability_bins(
    predictions: list[float],
    labels: list[int],
    *,
    num_bins: int = 10,
) -> list[ReliabilityBin]:
    """Bucket predictions and report calibration per bucket.

    We use equal-width bins from 0 to 1. The last bin is closed on the
    right so a prediction of exactly ``1.0`` is included.
    """
    if len(predictions) != len(labels):
        raise ValueError("predictions and labels must have the same length")
    if num_bins <= 0:
        raise ValueError("num_bins must be positive")

    width = 1.0 / num_bins
    bins: list[ReliabilityBin] = []
    for index in range(num_bins):
        lower = index * width
        upper = (index + 1) * width
        is_last = index == num_bins - 1

        bucket_preds: list[float] = []
        bucket_labels: list[int] = []
        for prediction, label in zip(predictions, labels):
            clipped = max(0.0, min(1.0, float(prediction)))
            in_bucket = (
                lower <= clipped <= upper if is_last else lower <= clipped < upper
            )
            if in_bucket:
                bucket_preds.append(clipped)
                bucket_labels.append(int(label))

        sample_size = len(bucket_preds)
        mean_predicted = round(sum(bucket_preds) / sample_size, 4) if sample_size else 0.0
        fraction_positive = (
            round(sum(bucket_labels) / sample_size, 4) if sample_size else 0.0
        )
        bins.append(
            ReliabilityBin(
                bin_lower=round(lower, 4),
                bin_upper=round(upper, 4),
                sample_size=sample_size,
                mean_predicted=mean_predicted,
                fraction_positive=fraction_positive,
            )
        )
    return bins


def walk_forward_predictions(
    frame,
    predictor,
    *,
    warmup: int = 60,
    horizon_days: int = 5,
    step_days: int = 1,
) -> tuple[list[float], list[int]]:
    """Run ``predictor`` against each anchor day and produce paired arrays.

    ``frame`` is a pandas DataFrame ordered by date ascending with at least
    a ``Close`` column. ``predictor(frame_slice) -> float`` must return a
    probability in ``[0, 1]`` for "up after horizon_days".

    Errors raised by ``predictor`` are skipped so a single bad day doesn't
    abort the whole walk-forward.
    """
    predictions, labels, _ = walk_forward_with_dates(
        frame, predictor, warmup=warmup, horizon_days=horizon_days, step_days=step_days
    )
    return predictions, labels


def walk_forward_with_dates(
    frame,
    predictor,
    *,
    warmup: int = 60,
    horizon_days: int = 5,
    step_days: int = 1,
) -> tuple[list[float], list[int], list]:
    """Same as :func:`walk_forward_predictions` but also returns anchor dates.

    Returns ``(predictions, labels, dates)`` where ``dates`` are the index
    values from ``frame`` at each anchor position.
    """
    closes = list(frame["Close"]) if "Close" in frame.columns else []
    index = list(frame.index)
    n = len(closes)
    predictions: list[float] = []
    labels: list[int] = []
    dates: list = []

    if n <= warmup + horizon_days:
        return predictions, labels, dates

    for anchor in range(warmup, n - horizon_days, max(1, step_days)):
        slice_frame = frame.iloc[: anchor + 1]
        try:
            probability_up = float(predictor(slice_frame))
        except Exception:
            continue
        future_close = float(closes[anchor + horizon_days])
        anchor_close = float(closes[anchor])
        if anchor_close <= 0:
            continue
        label = 1 if future_close > anchor_close else 0
        predictions.append(probability_up)
        labels.append(label)
        dates.append(index[anchor])

    return predictions, labels, dates
