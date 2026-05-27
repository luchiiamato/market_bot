from __future__ import annotations

from math import isfinite

import pandas as pd

from ..contracts import DeterministicSignal, Direction, Horizon


def generate_deterministic_signal(data: pd.DataFrame, horizon: Horizon) -> DeterministicSignal:
    latest = data.iloc[-1]
    price = float(latest["Close"])
    atr = _safe_number(latest["atr"], fallback=max(price * 0.02, 0.01))
    support = _safe_number(latest["support_20"], fallback=price - atr)
    resistance = _safe_number(latest["resistance_20"], fallback=price + atr)
    rsi = _safe_number(latest["rsi"], fallback=50.0)
    adx = _safe_number(latest["adx"], fallback=15.0)
    volume_ratio = _safe_number(latest["volume_ratio"], fallback=1.0)
    macd = _safe_number(latest["macd"], fallback=0.0)
    macd_signal = _safe_number(latest["macd_signal"], fallback=0.0)

    score = 50.0
    reasons: list[str] = []

    if horizon is Horizon.SHORT:
        score, reasons = _score_short_horizon(latest, score, reasons)
    else:
        score, reasons = _score_long_horizon(latest, score, reasons)

    direction = _direction_from_score(score)
    regime = _determine_regime(latest)
    setup_name = _setup_name(direction, horizon, rsi, regime, volume_ratio)
    stop_loss, take_profit = _trade_levels(direction, price, atr, support, resistance, horizon)
    invalidation = _build_invalidation(direction, stop_loss, support, resistance)

    if adx < 18:
        reasons.append("ADX bajo: el mercado esta lateral y la señal pierde fiabilidad.")
    elif adx >= 25:
        reasons.append("ADX confirma que la tendencia tiene fuerza suficiente para seguir.")

    if volume_ratio > 1.5:
        reasons.append("El volumen esta muy por encima del promedio y valida el movimiento.")
    elif volume_ratio < 0.8:
        reasons.append("El volumen esta por debajo del promedio y exige mas confirmacion.")

    if macd > macd_signal:
        reasons.append("MACD arriba de la señal: momentum a favor del sesgo alcista.")
    else:
        reasons.append("MACD debajo de la señal: momentum a favor del sesgo bajista.")

    return DeterministicSignal(
        direction=direction,
        score=round(max(0.0, min(100.0, score)), 2),
        regime=regime,
        setup_name=setup_name,
        invalidation=invalidation,
        reasons=reasons,
        stop_loss=round(stop_loss, 2) if stop_loss is not None else None,
        take_profit=round(take_profit, 2) if take_profit is not None else None,
    )


def _score_short_horizon(latest: pd.Series, score: float, reasons: list[str]):
    ema_9 = _safe_number(latest["ema_9"], fallback=latest["Close"])
    ema_20 = _safe_number(latest["ema_20"], fallback=latest["Close"])
    ema_50 = _safe_number(latest["ema_50"], fallback=latest["Close"])
    ema_200 = _safe_number(latest["ema_200"], fallback=latest["Close"])
    price = _safe_number(latest["Close"], fallback=0.0)
    rsi = _safe_number(latest["rsi"], fallback=50.0)
    stoch_k = _safe_number(latest["stoch_k"], fallback=50.0)
    stoch_d = _safe_number(latest["stoch_d"], fallback=50.0)
    support = _safe_number(latest["support_20"], fallback=price)
    resistance = _safe_number(latest["resistance_20"], fallback=price)
    volume_ratio = _safe_number(latest["volume_ratio"], fallback=1.0)

    if ema_9 > ema_20:
        score += 8
        reasons.append("EMA 9 arriba de EMA 20: impulso corto alcista.")
    else:
        score -= 8
        reasons.append("EMA 9 abajo de EMA 20: impulso corto debilitado.")

    if ema_20 > ema_50:
        score += 6
        reasons.append("EMA 20 arriba de EMA 50: continuidad de tendencia en swing.")
    else:
        score -= 6
        reasons.append("EMA 20 abajo de EMA 50: sesgo de swing mas debil.")

    if price > ema_200:
        score += 7
        reasons.append("Precio arriba de EMA 200: estructura mayor todavia acompana.")
    else:
        score -= 7
        reasons.append("Precio abajo de EMA 200: el corto esta contra la estructura mayor.")

    if rsi < 35 and price >= support:
        score += 6
        reasons.append("RSI comprimido cerca de soporte: setup de mean reversion posible.")
    elif rsi > 72:
        score -= 8
        reasons.append("RSI alto en corto plazo: riesgo de pullback inmediato.")

    if stoch_k < 20 and stoch_k > stoch_d:
        score += 4
        reasons.append("Stochastic gira desde sobreventa y acompana un rebote tactico.")
    elif stoch_k > 80 and stoch_k < stoch_d:
        score -= 4
        reasons.append("Stochastic gira desde sobrecompra y advierte fatiga.")

    if price > resistance and volume_ratio > 1.1:
        score += 7
        reasons.append("Ruptura de resistencia con volumen: continuation setup.")
    elif price < support:
        score -= 9
        reasons.append("Quiebre de soporte reciente: el tape corto se dano.")

    return score, reasons


def _score_long_horizon(latest: pd.Series, score: float, reasons: list[str]):
    price = _safe_number(latest["Close"], fallback=0.0)
    sma_20 = _safe_number(latest["sma_20"], fallback=price)
    sma_50 = _safe_number(latest["sma_50"], fallback=price)
    sma_200 = _safe_number(latest["sma_200"], fallback=price)
    rsi = _safe_number(latest["rsi"], fallback=50.0)
    bb_upper = _safe_number(latest["bb_upper"], fallback=price)
    bb_lower = _safe_number(latest["bb_lower"], fallback=price)
    volume_ratio = _safe_number(latest["volume_ratio"], fallback=1.0)
    price_vs_sma50 = _safe_number(latest["price_vs_sma50_pct"], fallback=0.0)

    if price > sma_200:
        score += 10
        reasons.append("Precio arriba de SMA 200: tendencia primaria alcista.")
    else:
        score -= 10
        reasons.append("Precio abajo de SMA 200: tendencia primaria fragil o bajista.")

    if sma_20 > sma_50 > sma_200:
        score += 10
        reasons.append("Medias largas alineadas en orden alcista.")
    elif sma_20 < sma_50 < sma_200:
        score -= 10
        reasons.append("Medias largas alineadas en orden bajista.")

    if 40 <= rsi <= 68:
        score += 6
        reasons.append("RSI de largo plazo sano: no hay sobreextension extrema.")
    elif rsi < 35:
        score += 4
        reasons.append("RSI bajo con estructura larga aun viva: posible ventana de acumulacion.")
    elif rsi > 75:
        score -= 7
        reasons.append("RSI muy alto de largo plazo: entrada nueva menos eficiente.")

    if price_vs_sma50 > 8:
        score -= 5
        reasons.append("Precio muy alejado de SMA 50: riesgo de regreso a la media.")
    elif price_vs_sma50 < -8:
        score += 3
        reasons.append("Precio muy comprimido frente a SMA 50: posible mejora de timing.")

    if price < bb_lower:
        score += 4
        reasons.append("Precio debajo de la banda inferior: compresion atractiva si la tesis aguanta.")
    elif price > bb_upper:
        score -= 4
        reasons.append("Precio arriba de la banda superior: extension que pide paciencia.")

    if volume_ratio > 1.2:
        score += 3
        reasons.append("Volumen acompana la estructura de fondo.")

    return score, reasons


def _determine_regime(latest: pd.Series) -> str:
    price = _safe_number(latest["Close"], fallback=0.0)
    ema_20 = _safe_number(latest.get("ema_20", price), fallback=price)
    sma_200 = _safe_number(latest["sma_200"], fallback=price)
    if price > sma_200 and ema_20 >= price * 0.97:
        return "uptrend"
    if price < sma_200 and ema_20 <= price * 1.03:
        return "downtrend"
    return "range"


def _direction_from_score(score: float) -> Direction:
    if score >= 60:
        return Direction.LONG
    if score <= 40:
        return Direction.SHORT
    return Direction.NEUTRAL


def _setup_name(
    direction: Direction,
    horizon: Horizon,
    rsi: float,
    regime: str,
    volume_ratio: float,
) -> str:
    if horizon is Horizon.SHORT:
        if direction is Direction.LONG and rsi < 40:
            return "mean_reversion_long"
        if direction is Direction.LONG and volume_ratio > 1.1:
            return "momentum_continuation_long"
        if direction is Direction.SHORT and regime == "downtrend":
            return "breakdown_short"
        return "mixed_short_setup"

    if direction is Direction.LONG:
        return "structural_uptrend"
    if direction is Direction.SHORT:
        return "structural_weakness"
    return "long_range_wait"


def _trade_levels(
    direction: Direction,
    price: float,
    atr: float,
    support: float,
    resistance: float,
    horizon: Horizon,
):
    if direction is Direction.NEUTRAL:
        return None, None

    tp_multiplier = 2.5 if horizon is Horizon.SHORT else 4.0
    stop_buffer = 1.4 if horizon is Horizon.SHORT else 2.0

    if direction is Direction.LONG:
        stop_loss = min(price - (atr * stop_buffer), support - (atr * 0.25))
        take_profit = price + (atr * tp_multiplier)
        return stop_loss, take_profit

    stop_loss = max(price + (atr * stop_buffer), resistance + (atr * 0.25))
    take_profit = price - (atr * tp_multiplier)
    return stop_loss, take_profit


def _build_invalidation(
    direction: Direction,
    stop_loss: float | None,
    support: float,
    resistance: float,
) -> str:
    if direction is Direction.LONG and stop_loss is not None:
        return (
            f"Perder {stop_loss:.2f} o cerrar debajo del soporte reciente "
            f"({support:.2f}) invalida la lectura alcista."
        )
    if direction is Direction.SHORT and stop_loss is not None:
        return (
            f"Recuperar {stop_loss:.2f} o romper la resistencia reciente "
            f"({resistance:.2f}) invalida la lectura bajista."
        )
    return "Esperar confirmacion adicional antes de comprometer capital."


def _safe_number(value, fallback: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return fallback
    return numeric if isfinite(numeric) else fallback
