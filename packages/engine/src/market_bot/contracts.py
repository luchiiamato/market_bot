from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Horizon(str, Enum):
    SHORT = "short"
    LONG = "long"


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class ActionType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    GO_LONG = "go_long"
    GO_SHORT = "go_short"
    LONG_PUT = "long_put"
    COVERED_CALL = "covered_call"
    CASH_SECURED_PUT = "cash_secured_put"
    AVOID = "avoid"


@dataclass
class IndicatorSnapshot:
    price: float
    rsi: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    adx: float | None = None
    atr: float | None = None
    volume_ratio: float | None = None
    sma_20: float | None = None
    sma_50: float | None = None
    sma_200: float | None = None
    bb_upper: float | None = None
    bb_lower: float | None = None
    support: float | None = None
    resistance: float | None = None


@dataclass
class DeterministicSignal:
    direction: Direction
    score: float
    regime: str
    setup_name: str
    invalidation: str
    reasons: list[str] = field(default_factory=list)
    stop_loss: float | None = None
    take_profit: float | None = None


@dataclass
class ScenarioProbability:
    label: str
    probability: float
    thesis: str


@dataclass
class ProbabilisticSignal:
    confidence: float
    probability_up: float
    scenarios: list[ScenarioProbability] = field(default_factory=list)
    dominant_features: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ModelValidationSummary:
    split_strategy: str
    calibration_method: str
    sample_size: int
    train_size: int
    test_size: int
    accuracy: float
    precision: float
    recall: float
    f1: float
    brier_score: float
    notes: list[str] = field(default_factory=list)


@dataclass
class BacktestSummary:
    strategy_name: str
    execution_model: str
    starting_cash: float
    ending_cash: float
    total_return_pct: float
    max_drawdown_pct: float
    total_trades: int
    win_rate_pct: float
    expectancy: float
    fee_bps: float
    slippage_bps: float


@dataclass
class ActionSuggestion:
    action: ActionType
    conviction: float
    rationale: str
    suitable_for: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


@dataclass
class Catalyst:
    name: str
    category: str
    impact: str


@dataclass
class TickerAnalysis:
    ticker: str
    horizon: Horizon
    generated_at: datetime
    indicators: IndicatorSnapshot
    deterministic: DeterministicSignal
    probabilistic: ProbabilisticSignal
    validation: ModelValidationSummary | None = None
    backtest: BacktestSummary | None = None
    actions: list[ActionSuggestion] = field(default_factory=list)
    catalysts: list[Catalyst] = field(default_factory=list)
    guardrails: list[str] = field(default_factory=list)
