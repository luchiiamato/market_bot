from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..contracts import (
    DeterministicSignal,
    Horizon,
    IndicatorSnapshot,
    ModelValidationSummary,
    ProbabilisticSignal,
    ScenarioProbability,
)


@dataclass
class ProbabilisticOutput:
    signal: ProbabilisticSignal
    validation: ModelValidationSummary


# Sprint 9.1: cuántas barras hacia adelante predice el modelo, por horizonte.
# Antes el target era el PRÓXIMO bar (shift(-1)): para SHORT eso es la próxima
# HORA (data 1h) = ruido de microestructura, por eso el F1 daba ~azar. Ahora
# predecimos la dirección del retorno A HORIZONTE, que es lo que el user pide y
# lo que sí es aprendible. SHORT (1h) ~5 ruedas = 35 barras; LONG (1d) ~20 ruedas.
_TARGET_HORIZON_BARS = {Horizon.SHORT: 35, Horizon.LONG: 20}


def target_horizon_bars(horizon: Horizon) -> int:
    return _TARGET_HORIZON_BARS.get(horizon, 5)


FEATURE_CAP = 5.0
FEATURE_LABELS = {
    "rsi_centered": "RSI",
    "macd_pct": "MACD",
    "macd_signal_pct": "senal MACD",
    "adx_norm": "ADX",
    "atr_pct": "ATR relativo",
    "volume_ratio_delta": "desvio de volumen",
    "stoch_k_centered": "stochastic K",
    "stoch_d_centered": "stochastic D",
    "momentum_10_pct": "momentum 10 barras",
    "price_vs_sma50_pct": "desvio contra SMA 50",
    "ema_9_20_gap_pct": "gap EMA 9/20",
    "ema_20_50_gap_pct": "gap EMA 20/50",
    "ema_50_200_gap_pct": "gap EMA 50/200",
    "close_vs_ema200_pct": "desvio contra EMA 200",
}


def generate_probabilistic_signal(
    data: pd.DataFrame,
    indicators: IndicatorSnapshot,
    deterministic: DeterministicSignal,
    horizon: Horizon,
) -> ProbabilisticOutput:
    try:
        return _generate_validated_signal(data, indicators, deterministic, horizon)
    except Exception as exc:
        return _fallback_output(indicators, deterministic, str(exc))


def _generate_validated_signal(
    data: pd.DataFrame,
    indicators: IndicatorSnapshot,
    deterministic: DeterministicSignal,
    horizon: Horizon,
) -> ProbabilisticOutput:
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, brier_score_loss, f1_score, precision_score, recall_score
    from sklearn.model_selection import TimeSeriesSplit

    feature_frame = _build_feature_frame(data)
    current_features = feature_frame.iloc[[-1]].copy()
    training_frame = data.loc[feature_frame.index].copy()
    # Sprint 9.1: target = dirección del retorno a HORIZONTE (no del próximo bar).
    horizon_bars = target_horizon_bars(horizon)
    training_frame["target"] = (
        training_frame["Close"].shift(-horizon_bars) > training_frame["Close"]
    ).astype(float)
    # Las últimas `horizon_bars` filas no tienen futuro conocido → dropna las saca.
    modeling_frame = feature_frame.join(training_frame["target"]).dropna().copy()

    if len(modeling_frame) < 180:
        raise ValueError("Muestra insuficiente para validacion temporal estable.")

    X = modeling_frame.drop(columns=["target"])
    y = modeling_frame["target"].astype(int)
    if y.nunique() < 2:
        raise ValueError("La serie no tiene variedad suficiente entre alza y baja para entrenar.")

    test_size = max(40, int(len(X) * 0.2))
    if len(X) - test_size < 120:
        raise ValueError("La ventana train/test queda demasiado corta para un split temporal valido.")

    X_train = X.iloc[:-test_size]
    y_train = y.iloc[:-test_size]
    X_test = X.iloc[-test_size:]
    y_test = y.iloc[-test_size:]
    if y_train.nunique() < 2 or y_test.nunique() < 2:
        raise ValueError("El split temporal quedo con una sola clase en train o test.")

    def build_estimator() -> RandomForestClassifier:
        return RandomForestClassifier(
            n_estimators=120,
            max_depth=5,
            min_samples_leaf=8,
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=1,
        )

    split_count = _resolve_split_count(y_train, TimeSeriesSplit)
    validation_model = CalibratedClassifierCV(
        estimator=build_estimator(),
        method="sigmoid",
        cv=TimeSeriesSplit(n_splits=split_count),
    )
    with warnings.catch_warnings():
        warnings.filterwarnings("error", category=RuntimeWarning)
        validation_model.fit(X_train, y_train)
    test_probabilities = validation_model.predict_proba(X_test)[:, 1]
    test_predictions = (test_probabilities >= 0.5).astype(int)

    accuracy = float(accuracy_score(y_test, test_predictions))
    precision = float(precision_score(y_test, test_predictions, zero_division=0))
    recall = float(recall_score(y_test, test_predictions, zero_division=0))
    f1 = float(f1_score(y_test, test_predictions, zero_division=0))
    brier = float(brier_score_loss(y_test, test_probabilities))

    production_split_count = _resolve_split_count(y, TimeSeriesSplit)
    production_model = CalibratedClassifierCV(
        estimator=build_estimator(),
        method="sigmoid",
        cv=TimeSeriesSplit(n_splits=production_split_count),
    )
    with warnings.catch_warnings():
        warnings.filterwarnings("error", category=RuntimeWarning)
        production_model.fit(X, y)
    probability_up = float(production_model.predict_proba(current_features)[0][1])

    explainer_model = build_estimator()
    explainer_model.fit(X, y)
    dominant_features = _dominant_features(explainer_model, current_features.iloc[0], X, y)
    confidence = _confidence(probability_up, f1, brier)

    scenarios = _scenarios(probability_up, horizon)
    signal_warnings = []
    if test_size < 60:
        signal_warnings.append("La ventana de test es relativamente corta. Revisar estabilidad por mas tiempo.")
    if brier > 0.24:
        signal_warnings.append("La calibracion aun es debil. Tomar la confianza como orientativa.")
    if f1 < 0.48:
        signal_warnings.append("El modelo supera apenas al azar. Usar el motor deterministico como referencia principal.")
    # Sprint 9.2b honesty: F1 can look fine while accuracy sits at chance (class
    # imbalance — markets drift up). Gate the user-facing claim on ACCURACY too,
    # so the probability is presented as orientative, never as a hard signal.
    if accuracy < 0.52:
        signal_warnings.append(
            "El modelo no le gana al azar en aciertos (accuracy ~50%). Tratá la probabilidad "
            "como orientativa, no como señal: priorizá el motor determinístico, catalysts y tu criterio."
        )

    validation = ModelValidationSummary(
        split_strategy="chronological_holdout_plus_timeseriessplit",
        calibration_method="sigmoid",
        sample_size=int(len(X)),
        train_size=int(len(X_train)),
        test_size=int(len(X_test)),
        accuracy=round(accuracy, 3),
        precision=round(precision, 3),
        recall=round(recall, 3),
        f1=round(f1, 3),
        brier_score=round(brier, 3),
        notes=[
            "Se entreno un random forest calibrado con TimeSeriesSplit sobre features normalizadas.",
            f"El target es la direccion del retorno a {horizon_bars} barras (horizonte {horizon.value}), no del proximo bar.",
        ],
    )

    signal = ProbabilisticSignal(
        confidence=round(confidence, 2),
        probability_up=round(probability_up, 2),
        scenarios=scenarios,
        dominant_features=dominant_features,
        warnings=signal_warnings,
    )

    return ProbabilisticOutput(signal=signal, validation=validation)


def _build_feature_frame(data: pd.DataFrame) -> pd.DataFrame:
    close = data["Close"].replace(0.0, np.nan)
    features = pd.DataFrame(index=data.index)

    features["rsi_centered"] = (data["rsi"] - 50.0) / 50.0
    features["macd_pct"] = data["macd"] / close
    features["macd_signal_pct"] = data["macd_signal"] / close
    features["adx_norm"] = data["adx"] / 100.0
    features["atr_pct"] = data["atr"] / close
    features["volume_ratio_delta"] = data["volume_ratio"] - 1.0
    features["stoch_k_centered"] = (data["stoch_k"] - 50.0) / 50.0
    features["stoch_d_centered"] = (data["stoch_d"] - 50.0) / 50.0
    features["momentum_10_pct"] = data["momentum_10"] / close
    features["price_vs_sma50_pct"] = data["price_vs_sma50_pct"] / 100.0
    features["ema_9_20_gap_pct"] = (data["ema_9"] - data["ema_20"]) / close
    features["ema_20_50_gap_pct"] = (data["ema_20"] - data["ema_50"]) / close
    features["ema_50_200_gap_pct"] = (data["ema_50"] - data["ema_200"]) / close
    features["close_vs_ema200_pct"] = (close - data["ema_200"]) / close

    cleaned = (
        features.replace([np.inf, -np.inf], np.nan)
        .ffill()
        .bfill()
        .dropna()
        .clip(lower=-FEATURE_CAP, upper=FEATURE_CAP)
    )
    if cleaned.empty:
        raise ValueError("No se pudieron construir features numericas limpias.")
    return cleaned


def _resolve_split_count(target: pd.Series, splitter_cls) -> int:
    max_candidate = min(5, max(2, len(target) // 60))
    for split_count in range(max_candidate, 1, -1):
        splitter = splitter_cls(n_splits=split_count)
        if _split_supports_both_classes(target, splitter):
            return split_count
    raise ValueError("La serie no tiene suficiente variedad temporal para calibrar el modelo.")


def _split_supports_both_classes(target: pd.Series, splitter) -> bool:
    for train_idx, test_idx in splitter.split(target):
        if target.iloc[train_idx].nunique() < 2:
            return False
        if target.iloc[test_idx].nunique() < 2:
            return False
    return True


def _confidence(probability_up: float, f1: float, brier: float) -> float:
    distance = abs(probability_up - 0.5)
    quality = max(0.0, f1 - 0.5)
    calibration_bonus = max(0.0, 0.26 - brier)
    confidence = 0.48 + (distance * 0.9) + (quality * 0.5) + (calibration_bonus * 0.4)
    return max(0.5, min(0.92, confidence))


def _scenarios(probability_up: float, horizon: Horizon) -> list[ScenarioProbability]:
    base_probability = max(0.14, 0.34 - abs(probability_up - 0.5) * 0.32)
    bull_probability = max(0.05, probability_up - (base_probability / 2))
    bear_probability = max(0.05, (1 - probability_up) - (base_probability / 2))
    normalization = bull_probability + bear_probability + base_probability
    bull_probability /= normalization
    bear_probability /= normalization
    base_probability /= normalization

    bull_thesis = (
        "Continuacion positiva del sesgo de corto plazo."
        if horizon is Horizon.SHORT
        else "Persistencia de la estructura alcista en el marco largo."
    )
    bear_thesis = (
        "Fallo del setup actual y rotacion hacia debilidad tactica."
        if horizon is Horizon.SHORT
        else "Deterioro de la estructura mayor y perdida de tesis."
    )

    return [
        ScenarioProbability(label="bull", probability=round(bull_probability, 2), thesis=bull_thesis),
        ScenarioProbability(
            label="base",
            probability=round(base_probability, 2),
            thesis="Lateralidad o digestion antes del proximo movimiento direccional.",
        ),
        ScenarioProbability(label="bear", probability=round(bear_probability, 2), thesis=bear_thesis),
    ]


def _dominant_features(
    model,
    current_features: pd.Series,
    X: pd.DataFrame,
    y: pd.Series,
) -> list[str]:
    importances = pd.Series(model.feature_importances_, index=X.columns)
    bullish_means = X.loc[y == 1].mean()
    bearish_means = X.loc[y == 0].mean()
    midpoint = (bullish_means + bearish_means) / 2
    directional_edge = np.sign(bullish_means - bearish_means).replace(0.0, 1.0)
    contributions = importances * (current_features.reindex(X.columns) - midpoint) * directional_edge
    ranked = contributions.abs().sort_values(ascending=False).head(3).index.tolist()
    explanations = []
    for feature_name in ranked:
        contribution = float(contributions.loc[feature_name])
        direction = "apoya al alza" if contribution >= 0 else "apoya a la baja"
        label = FEATURE_LABELS.get(feature_name, feature_name)
        explanations.append(f"{label} {direction}")
    return explanations


def _fallback_output(
    indicators: IndicatorSnapshot,
    deterministic: DeterministicSignal,
    reason: str,
) -> ProbabilisticOutput:
    probability_up = 0.5 + ((deterministic.score - 50.0) / 100.0) * 0.55
    probability_up = max(0.1, min(0.9, probability_up))

    signal = ProbabilisticSignal(
        confidence=0.52,
        probability_up=round(probability_up, 2),
        scenarios=[
            ScenarioProbability(label="bull", probability=round(max(0.2, probability_up - 0.1), 2), thesis="Fallback bullish path."),
            ScenarioProbability(label="base", probability=0.3, thesis="Fallback base path."),
            ScenarioProbability(label="bear", probability=round(max(0.2, 1 - probability_up - 0.1), 2), thesis="Fallback bearish path."),
        ],
        dominant_features=deterministic.reasons[:3],
        warnings=[f"Se uso fallback heuristico: {reason}"],
    )
    validation = ModelValidationSummary(
        split_strategy="fallback",
        calibration_method="none",
        sample_size=0,
        train_size=0,
        test_size=0,
        accuracy=0.0,
        precision=0.0,
        recall=0.0,
        f1=0.0,
        brier_score=0.0,
        notes=["No se pudo correr validacion temporal completa."],
    )
    return ProbabilisticOutput(signal=signal, validation=validation)
