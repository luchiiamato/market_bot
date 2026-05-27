from __future__ import annotations

from ..contracts import ActionSuggestion, ActionType, DeterministicSignal, Horizon, ProbabilisticSignal


def suggest_actions(
    horizon: Horizon,
    deterministic: DeterministicSignal,
    probabilistic: ProbabilisticSignal,
) -> list[ActionSuggestion]:
    if horizon is Horizon.SHORT:
        return _short_horizon_actions(deterministic, probabilistic)
    return _long_horizon_actions(deterministic, probabilistic)


def rank_score(deterministic: DeterministicSignal, probabilistic: ProbabilisticSignal) -> float:
    return round((deterministic.score * 0.65) + (probabilistic.confidence * 35), 2)


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
