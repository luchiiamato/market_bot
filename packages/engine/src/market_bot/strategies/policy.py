from __future__ import annotations

from dataclasses import dataclass

from ..contracts import (
    ActionSuggestion,
    ActionType,
    Catalyst,
    CatalystStatus,
    DeterministicSignal,
    Horizon,
    ProbabilisticSignal,
    TickerAnalysis,
)


# Actions that involve shorting or option-shorting. Excluded for conservative
# profiles regardless of signal direction.
DIRECTIONAL_SHORT_ACTIONS = {
    ActionType.GO_SHORT,
    ActionType.LONG_PUT,
    ActionType.COVERED_CALL,
    ActionType.CASH_SECURED_PUT,
}


@dataclass(frozen=True)
class ProfileFilter:
    """Resolved view of an investor profile for ranking / action filtering."""

    investor_profile: str = "moderate"
    risk_tolerance: str = "medium"
    preferred_horizon: str = "mixed"
    preferred_instrument_types: str = "both"

    @property
    def is_conservative(self) -> bool:
        return self.investor_profile == "conservative" or self.risk_tolerance == "low"

    @property
    def is_aggressive(self) -> bool:
        return self.investor_profile == "aggressive" or self.risk_tolerance == "high"


def suggest_actions(
    horizon: Horizon,
    deterministic: DeterministicSignal,
    probabilistic: ProbabilisticSignal,
    profile: ProfileFilter | None = None,
) -> list[ActionSuggestion]:
    base = (
        _short_horizon_actions(deterministic, probabilistic)
        if horizon is Horizon.SHORT
        else _long_horizon_actions(deterministic, probabilistic)
    )
    if profile is None:
        return base
    return _filter_actions_for_profile(base, profile)


def rank_score(deterministic: DeterministicSignal, probabilistic: ProbabilisticSignal) -> float:
    return round((deterministic.score * 0.65) + (probabilistic.confidence * 35), 2)


def adjust_rank_for_profile(base_score: float, analysis: TickerAnalysis, profile: ProfileFilter) -> float:
    """Reweight a base rank score by how well it matches the profile."""
    adjusted = base_score
    indicators = analysis.indicators

    # Penalise high-volatility names for low-risk users.
    if profile.is_conservative and indicators.atr and indicators.price:
        vol_ratio = indicators.atr / indicators.price
        if vol_ratio > 0.04:
            adjusted *= 0.6
    # Reward conviction for aggressive users.
    if profile.is_aggressive and analysis.probabilistic.confidence > 0.7:
        adjusted *= 1.15
    # Conservative users get a smaller bonus when probabilistic confidence is high too.
    if profile.is_conservative and analysis.probabilistic.confidence > 0.65 and not _has_rumor_only(analysis.catalysts):
        adjusted *= 1.05
    return round(adjusted, 2)


def passes_profile_filter(analysis: TickerAnalysis, profile: ProfileFilter) -> bool:
    """Hard filter: should this ticker even appear in the ranking?"""
    if profile.is_conservative:
        # Drop tickers driven entirely by rumored catalysts — they're too noisy.
        if _has_rumor_only(analysis.catalysts):
            return False
        # Drop extreme realised volatility.
        if analysis.indicators.atr and analysis.indicators.price:
            if (analysis.indicators.atr / analysis.indicators.price) > 0.06:
                return False
    return True


def compute_why_for_you(analysis: TickerAnalysis, profile: ProfileFilter) -> list[str]:
    """Build short human-readable reasons explaining why a ticker matches."""
    reasons: list[str] = []

    # Profile-direction match.
    direction = analysis.deterministic.direction.value
    if direction == "long" and not profile.is_conservative:
        reasons.append("Setup direccional alcista alineado a tu perfil.")
    if direction == "long" and profile.is_conservative:
        reasons.append("Setup alcista limpio para perfil conservador.")
    if direction == "short" and profile.is_aggressive:
        reasons.append("Estructura bajista — apto solo si toleras squeezes.")

    # Conviction.
    conf = analysis.probabilistic.confidence
    if conf >= 0.75:
        reasons.append(f"Conviccion alta del modelo ({conf:.2f}).")
    elif conf <= 0.45 and profile.is_conservative:
        reasons.append("Conviccion baja — esperar mejor entrada.")

    # Catalyst status.
    confirmed = [c for c in analysis.catalysts if c.status == CatalystStatus.CONFIRMED]
    rumored = [c for c in analysis.catalysts if c.status == CatalystStatus.RUMORED]
    if confirmed:
        next_event = next((c for c in confirmed if c.category == "earnings"), None)
        if next_event:
            reasons.append(f"Earnings event confirmado: {next_event.name[:60]}.")
    if rumored and not profile.is_aggressive:
        reasons.append("Hay rumores en juego — mantenelo bajo observacion.")

    # Volatility check for risk-aligned narrative.
    indicators = analysis.indicators
    if indicators.atr and indicators.price:
        vol_ratio = indicators.atr / indicators.price
        if vol_ratio > 0.04 and profile.is_aggressive:
            reasons.append("Volatilidad alta — apto para perfil agresivo.")
        if vol_ratio < 0.02 and profile.is_conservative:
            reasons.append("Volatilidad controlada — ajustado a tu tolerancia.")

    return reasons[:3]


def _filter_actions_for_profile(
    actions: list[ActionSuggestion], profile: ProfileFilter
) -> list[ActionSuggestion]:
    if not profile.is_conservative:
        return actions
    # Conservative profile: strip short / put / covered call alternatives.
    filtered = [a for a in actions if a.action not in DIRECTIONAL_SHORT_ACTIONS]
    if not filtered:
        # Ensure at least an AVOID option remains so the caller has something.
        filtered = [
            ActionSuggestion(
                action=ActionType.AVOID,
                conviction=0.5,
                rationale="Tu perfil conservador no habilita las acciones direccionales disponibles aqui.",
            )
        ]
    return filtered


def _has_rumor_only(catalysts: list[Catalyst]) -> bool:
    if not catalysts:
        return False
    has_rumor = any(c.status == CatalystStatus.RUMORED for c in catalysts)
    has_credible = any(
        c.status in (CatalystStatus.CONFIRMED, CatalystStatus.REPORTED) for c in catalysts
    )
    return has_rumor and not has_credible


def _short_horizon_actions(
    deterministic: DeterministicSignal, probabilistic: ProbabilisticSignal
) -> list[ActionSuggestion]:
    if deterministic.direction.value == "long":
        return [
            ActionSuggestion(
                action=ActionType.GO_LONG,
                conviction=probabilistic.confidence,
                rationale="La lectura tactica favorece un long de corto plazo con invalidez clara.",
                suitable_for=["swing", "mean_reversion", "momentum"],
            ),
            ActionSuggestion(
                action=ActionType.HOLD,
                conviction=max(0.5, probabilistic.confidence - 0.08),
                rationale="Mantener solo si la posicion ya esta abierta y el stop sigue valido.",
            ),
            ActionSuggestion(
                action=ActionType.AVOID,
                conviction=0.45,
                rationale="Evitar si no toleras volatilidad intradiaria o gaps.",
            ),
        ]

    if deterministic.direction.value == "short":
        return [
            ActionSuggestion(
                action=ActionType.GO_SHORT,
                conviction=probabilistic.confidence,
                rationale="La estructura tactica favorece continuidad bajista o breakdown trade.",
                suitable_for=["breakdown", "intraday", "swing_short"],
            ),
            ActionSuggestion(
                action=ActionType.LONG_PUT,
                conviction=max(0.5, probabilistic.confidence - 0.03),
                rationale="Long put puede limitar el riesgo si existe una cadena liquida.",
                blockers=["Requiere verificar liquidez e IV de la opcion."],
            ),
            ActionSuggestion(
                action=ActionType.AVOID,
                conviction=0.42,
                rationale="Evitar si no aceptas squeezes o coberturas caras.",
            ),
        ]

    return [
        ActionSuggestion(
            action=ActionType.HOLD,
            conviction=0.5,
            rationale="La señal es mixta y conviene esperar confirmacion antes de operar.",
        ),
        ActionSuggestion(
            action=ActionType.AVOID,
            conviction=0.48,
            rationale="No hay suficiente edge tactico para justificar un trade nuevo.",
        ),
    ]


def _long_horizon_actions(
    deterministic: DeterministicSignal, probabilistic: ProbabilisticSignal
) -> list[ActionSuggestion]:
    if deterministic.direction.value == "long":
        return [
            ActionSuggestion(
                action=ActionType.BUY,
                conviction=probabilistic.confidence,
                rationale="La estructura de largo plazo justifica compra o acumulacion escalonada.",
                suitable_for=["position_trade", "core_position"],
            ),
            ActionSuggestion(
                action=ActionType.HOLD,
                conviction=max(0.55, probabilistic.confidence - 0.06),
                rationale="Mantener si la tesis ya esta viva y no se rompio la estructura mayor.",
            ),
            ActionSuggestion(
                action=ActionType.CASH_SECURED_PUT,
                conviction=max(0.5, probabilistic.confidence - 0.08),
                rationale="Alternativa defensiva si queres entrar a mejor precio con ingreso por prima.",
                blockers=["Solo si aceptas potencial asignacion."],
            ),
            ActionSuggestion(
                action=ActionType.COVERED_CALL,
                conviction=0.46,
                rationale="Puede servir si ya tenes acciones y esperas lateralidad temporal.",
            ),
        ]

    if deterministic.direction.value == "short":
        return [
            ActionSuggestion(
                action=ActionType.AVOID,
                conviction=probabilistic.confidence,
                rationale="La estructura larga no justifica iniciar una posicion core.",
            ),
            ActionSuggestion(
                action=ActionType.LONG_PUT,
                conviction=max(0.52, probabilistic.confidence - 0.04),
                rationale="Sirve para tesis bajista definida con perdida maxima acotada.",
                blockers=["Confirmar que la cadena tenga liquidez util."],
            ),
            ActionSuggestion(
                action=ActionType.HOLD,
                conviction=0.4,
                rationale="Si ya estabas comprado, reducir o revisar la tesis antes de mantener.",
            ),
        ]

    return [
        ActionSuggestion(
            action=ActionType.HOLD,
            conviction=0.5,
            rationale="La estructura no da una ventana clara para agregar riesgo nuevo.",
        ),
        ActionSuggestion(
            action=ActionType.AVOID,
            conviction=0.49,
            rationale="Esperar mejor timing o una ruptura mas limpia mejora la expectativa.",
        ),
    ]
