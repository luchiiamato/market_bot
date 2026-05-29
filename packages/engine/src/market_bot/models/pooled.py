"""Sprint 9.2 — Pooled cross-sectional probabilistic model.

Instead of training a fresh RandomForest per ticker (slow + overfits ~800 bars),
we train ONE calibrated model over the features of the WHOLE universe and infer
per ticker in milliseconds. Reuses the 9.1 horizon target and the existing
feature/scenario/confidence helpers from ``baseline.py``.

Scope: this powers the FAST path (analyze_ticker + ranking). The per-ticker
``generate_probabilistic_signal`` stays as a fallback, and ``/validation``
walk-forward stays per-ticker (so test_validation_brier is untouched).

NOT wired into the service yet — see docs/sprint-9.2-pooled-model.md steps 5-7.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd

from ..contracts import Horizon, ProbabilisticSignal, ModelValidationSummary
from ..indicators import compute_indicators
from .baseline import (
    _build_feature_frame,
    _confidence,
    _scenarios,
    target_horizon_bars,
)


@dataclass
class PooledArtifact:
    model: object  # trained CalibratedClassifierCV
    feature_columns: list[str]
    horizon: Horizon
    validation: ModelValidationSummary
    trained_at: datetime
    n_tickers: int
    n_samples: int
    importances: pd.Series = field(default=None)  # global feature importances
    bullish_means: pd.Series = field(default=None)
    bearish_means: pd.Series = field(default=None)


_Z_CLIP = 5.0


def _zscore_per_ticker(feats: pd.DataFrame) -> pd.DataFrame:
    """Normalize each feature by THIS ticker's own mean/std (Sprint 9.2b).

    Pooling raw features across 58 tickers mixes different scales/regimes, which
    is why the first pooled model scored f1≈0.42. Z-scoring per ticker makes the
    signals comparable across the universe. Inference must apply the SAME (this
    ticker's own) normalization — see predict_pooled.
    """
    mu = feats.mean()
    sd = feats.std(ddof=0).replace(0.0, 1.0)
    return ((feats - mu) / sd).clip(lower=-_Z_CLIP, upper=_Z_CLIP)


def build_pooled_dataset(adapter, universe: list[str], horizon: Horizon) -> pd.DataFrame:
    """Concatenate per-ticker (features + horizon target + date) across the universe.

    Soft-fails per ticker: a ticker that can't be fetched/featurised is skipped.
    Features are z-scored per ticker (9.2b) so scales are comparable when pooled.
    Returns a DataFrame with feature columns + ``target`` + ``__date`` + ``__ticker``.
    """
    horizon_bars = target_horizon_bars(horizon)
    frames: list[pd.DataFrame] = []
    for ticker in universe:
        try:
            price_history = adapter.get_price_history(ticker.upper(), horizon)
            data = compute_indicators(price_history.frame)
            feats = _zscore_per_ticker(_build_feature_frame(data))
            aligned = data.loc[feats.index]
            target = (aligned["Close"].shift(-horizon_bars) > aligned["Close"]).astype(float)
            block = feats.join(target.rename("target")).dropna().copy()
            if block.empty:
                continue
            block["__date"] = block.index
            block["__ticker"] = ticker.upper()
            frames.append(block)
        except Exception:
            # Skip the ticker; the pooled set is robust to a few drops.
            continue
    if not frames:
        raise ValueError("No se pudo construir el dataset pooled (ningún ticker válido).")
    return pd.concat(frames, ignore_index=True)


def train_pooled_model(adapter, universe: list[str], horizon: Horizon) -> PooledArtifact:
    """Train ONE calibrated RF over the pooled dataset with a TIME-based holdout.

    Critical: the train/test split is by DATE, not by row — a row-based split
    would mix one ticker's future with another's past (leakage).
    """
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import (
        accuracy_score,
        brier_score_loss,
        f1_score,
        precision_score,
        recall_score,
    )

    dataset = build_pooled_dataset(adapter, universe, horizon)
    feature_columns = [c for c in dataset.columns if c not in ("target", "__date", "__ticker")]

    # Time-based split: oldest ~80% of the DATE range = train, newest ~20% = test.
    dates = pd.to_datetime(dataset["__date"])
    cutoff = dates.quantile(0.8)
    train_mask = dates <= cutoff
    test_mask = ~train_mask

    X = dataset[feature_columns]
    y = dataset["target"].astype(int)
    X_train, y_train = X[train_mask], y[train_mask]
    X_test, y_test = X[test_mask], y[test_mask]

    if len(X_train) < 300 or y_train.nunique() < 2 or len(X_test) < 50 or y_test.nunique() < 2:
        raise ValueError("Dataset pooled insuficiente o sin variedad de clases para split temporal.")

    def build_estimator() -> "RandomForestClassifier":
        return RandomForestClassifier(
            n_estimators=200,
            max_depth=6,
            min_samples_leaf=20,
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=-1,
        )

    model = CalibratedClassifierCV(estimator=build_estimator(), method="sigmoid", cv=3)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore")
        model.fit(X_train, y_train)

    test_prob = model.predict_proba(X_test)[:, 1]
    test_pred = (test_prob >= 0.5).astype(int)

    # Global feature importances + class means for per-ticker explanations.
    explainer = build_estimator()
    explainer.fit(X, y)
    importances = pd.Series(explainer.feature_importances_, index=feature_columns)
    bullish_means = X.loc[y == 1].mean()
    bearish_means = X.loc[y == 0].mean()

    validation = ModelValidationSummary(
        split_strategy="pooled_cross_sectional_time_holdout",
        calibration_method="sigmoid",
        sample_size=int(len(X)),
        train_size=int(len(X_train)),
        test_size=int(len(X_test)),
        accuracy=round(float(accuracy_score(y_test, test_pred)), 3),
        precision=round(float(precision_score(y_test, test_pred, zero_division=0)), 3),
        recall=round(float(recall_score(y_test, test_pred, zero_division=0)), 3),
        f1=round(float(f1_score(y_test, test_pred, zero_division=0)), 3),
        brier_score=round(float(brier_score_loss(y_test, test_prob)), 3),
        notes=[
            f"Modelo pooled entrenado sobre {dataset['__ticker'].nunique()} tickers.",
            f"Target: direccion del retorno a {target_horizon_bars(horizon)} barras (horizonte {horizon.value}).",
            "Split temporal por fecha (no por row) para evitar leakage cross-ticker.",
        ],
    )

    return PooledArtifact(
        model=model,
        feature_columns=feature_columns,
        horizon=horizon,
        validation=validation,
        trained_at=datetime.utcnow(),
        n_tickers=int(dataset["__ticker"].nunique()),
        n_samples=int(len(X)),
        importances=importances,
        bullish_means=bullish_means,
        bearish_means=bearish_means,
    )


def predict_pooled(artifact: PooledArtifact, data: pd.DataFrame, horizon: Horizon) -> ProbabilisticSignal:
    """Infer probability_up for one ticker from its enriched price frame (ms)."""
    # Same per-ticker z-score as training (9.2b): normalize by THIS ticker's own
    # full-history stats so the current row is comparable to what the model saw.
    feats = _zscore_per_ticker(_build_feature_frame(data))
    current = feats.iloc[[-1]].reindex(columns=artifact.feature_columns)
    probability_up = float(artifact.model.predict_proba(current)[0][1])

    f1 = artifact.validation.f1
    brier = artifact.validation.brier_score
    confidence = _confidence(probability_up, f1, brier)
    scenarios = _scenarios(probability_up, horizon)

    dominant = _pooled_dominant_features(artifact, current.iloc[0])

    sig_warnings: list[str] = []
    if f1 < 0.52:
        sig_warnings.append("El modelo pooled supera apenas al azar. Usar el motor deterministico como referencia.")
    if brier > 0.25:
        sig_warnings.append("Calibracion debil del modelo pooled. Tomar la confianza como orientativa.")

    return ProbabilisticSignal(
        confidence=round(confidence, 2),
        probability_up=round(probability_up, 2),
        scenarios=scenarios,
        dominant_features=dominant,
        warnings=sig_warnings,
    )


def _pooled_dominant_features(artifact: PooledArtifact, current_features: pd.Series) -> list[str]:
    from .baseline import FEATURE_LABELS

    midpoint = (artifact.bullish_means + artifact.bearish_means) / 2
    edge = np.sign(artifact.bullish_means - artifact.bearish_means).replace(0.0, 1.0)
    contributions = artifact.importances * (current_features.reindex(artifact.feature_columns) - midpoint) * edge
    ranked = contributions.abs().sort_values(ascending=False).head(3).index.tolist()
    out = []
    for name in ranked:
        direction = "apoya al alza" if float(contributions.loc[name]) >= 0 else "apoya a la baja"
        out.append(f"{FEATURE_LABELS.get(name, name)} {direction}")
    return out
