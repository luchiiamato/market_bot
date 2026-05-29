from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

TICKER_PATTERN = r"^[A-Za-z0-9.\-]{1,16}$"


class AnalyzeRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=16, pattern=TICKER_PATTERN)
    horizon: str = Field(default="short", pattern="^(short|long)$")


class AiAnalysisRequest(AnalyzeRequest):
    pass


class AiAnalysisCitationResponse(BaseModel):
    title: str
    url: str
    source: Optional[str] = None
    published_at: Optional[str] = None


class AiAnalysisResponse(BaseModel):
    ticker: str
    horizon: str
    provider: str
    model: str
    content: str
    citations: list[AiAnalysisCitationResponse] = Field(default_factory=list)
    generated_at: datetime
    used_profile_context: bool = False


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=128)
    display_name: Optional[str] = Field(default=None, max_length=80)
    investor_profile: str = Field(default="moderate", pattern="^(conservative|moderate|aggressive)$")
    preferred_horizon: str = Field(default="mixed", pattern="^(short|long|mixed)$")
    preferred_instrument_types: str = Field(default="both", pattern="^(cedear|stock|both)$")
    risk_tolerance: str = Field(default="medium", pattern="^(low|medium|high)$")
    benchmark_preference: str = Field(default="mep", pattern="^(official|mep|ccl)$")


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=128)


class ProfileUpdateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    investor_profile: str = Field(pattern="^(conservative|moderate|aggressive)$")
    preferred_horizon: str = Field(pattern="^(short|long|mixed)$")
    preferred_instrument_types: str = Field(pattern="^(cedear|stock|both)$")
    risk_tolerance: str = Field(pattern="^(low|medium|high)$")
    benchmark_preference: str = Field(pattern="^(official|mep|ccl)$")


class CreatePositionRequest(BaseModel):
    instrument_type: str = Field(pattern="^(cedear|stock)$")
    symbol: str = Field(min_length=1, max_length=16, pattern=TICKER_PATTERN)
    quantity: float = Field(gt=0)
    purchase_date: date
    purchase_price: float = Field(gt=0)
    purchase_currency: str = Field(pattern="^(ARS|USD)$")
    underlying_ticker: Optional[str] = Field(default=None, max_length=16, pattern=TICKER_PATTERN)
    cedear_ratio: Optional[float] = Field(default=None, gt=0)
    notes: str = Field(default="", max_length=500)


class UpdatePositionRequest(CreatePositionRequest):
    pass


class ScenarioProbabilityResponse(BaseModel):
    label: str
    probability: float
    thesis: str


class ActionSuggestionResponse(BaseModel):
    action: str
    conviction: float
    rationale: str
    suitable_for: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class CatalystResponse(BaseModel):
    name: str
    category: str
    impact: str
    status: str = "inferred"
    source_url: Optional[str] = None
    observed_at: Optional[datetime] = None


class IndicatorSnapshotResponse(BaseModel):
    price: float
    rsi: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    adx: Optional[float] = None
    atr: Optional[float] = None
    volume_ratio: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_lower: Optional[float] = None
    support: Optional[float] = None
    resistance: Optional[float] = None


class DeterministicSignalResponse(BaseModel):
    direction: str
    score: float
    regime: str
    setup_name: str
    invalidation: str
    reasons: list[str]
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class ProbabilisticSignalResponse(BaseModel):
    confidence: float
    probability_up: float
    scenarios: list[ScenarioProbabilityResponse]
    dominant_features: list[str]
    warnings: list[str]


class ModelValidationResponse(BaseModel):
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
    notes: list[str]


class BacktestSummaryResponse(BaseModel):
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


class TickerAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    horizon: str
    generated_at: datetime
    indicators: IndicatorSnapshotResponse
    deterministic: DeterministicSignalResponse
    probabilistic: ProbabilisticSignalResponse
    validation: Optional[ModelValidationResponse] = None
    backtest: Optional[BacktestSummaryResponse] = None
    actions: list[ActionSuggestionResponse]
    catalysts: list[CatalystResponse]
    guardrails: list[str]


class RankingItemResponse(BaseModel):
    ticker: str
    action: str
    direction: str
    rank_score: float
    conviction: float
    price: float
    regime: str
    is_cedear: bool
    why_for_you: list[str] = Field(default_factory=list)


class UniverseItemResponse(BaseModel):
    ticker: str
    is_cedear: bool = True


class InvestorProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    username: str
    display_name: str
    local_currency: str
    investor_profile: str
    preferred_horizon: str
    preferred_instrument_types: str
    risk_tolerance: str
    benchmark_preference: str
    created_at: datetime
    updated_at: datetime


class SessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    profile: InvestorProfileResponse


class BenchmarkComparisonResponse(BaseModel):
    label: str
    tracked_value_ars: float
    outperformance_ars: float
    outperformance_pct: float


class PositionValuationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position_id: int
    instrument_type: str
    symbol: str
    underlying_ticker: str
    byma_symbol: Optional[str] = None
    cedear_ratio: Optional[float] = None
    cedear_ratio_source: Optional[str] = None
    quantity: float
    purchase_date: date
    purchase_price: float
    purchase_currency: str
    user_notes: str = ""
    current_price: float
    current_price_currency: str
    quote_as_of: date
    current_value_ars: float
    current_value_usd: float
    cost_basis_ars: float
    cost_basis_usd: float
    pnl_ars: float
    pnl_usd: float
    return_pct_ars: float
    return_pct_usd: float
    real_return_pct: float
    preferred_benchmark_return_pct: float = 0.0
    preferred_benchmark_label: str = "inflation"
    benchmark_comparisons: list[BenchmarkComparisonResponse]
    notes: list[str]


class ExposureBucketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str
    total_value_ars: float
    pct: float


class PortfolioSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    positions_count: int
    total_value_ars: float
    total_value_usd: float
    total_cost_ars: float
    total_cost_usd: float
    total_pnl_ars: float
    total_pnl_usd: float
    total_return_pct_ars: float
    total_return_pct_usd: float
    total_real_return_pct: float
    total_preferred_benchmark_return_pct: float = 0.0
    preferred_benchmark_label: str = "inflation"
    positions: list[PositionValuationResponse]
    sector_exposure: list[ExposureBucketResponse] = Field(default_factory=list)
    region_exposure: list[ExposureBucketResponse] = Field(default_factory=list)


class ExchangeRatesResponse(BaseModel):
    as_of: date
    official: float
    mep: float
    ccl: float
    source: str


class PeriodBenchmarkResponse(BaseModel):
    start_date: date
    end_date: date
    purchase_exchange: ExchangeRatesResponse
    current_exchange: ExchangeRatesResponse
    inflation_factor: float
    fixed_term_factor: float
    inflation_source: str
    rates_source: str
    fixed_term_source: str


class HealthResponse(BaseModel):
    status: str
    service: str


class NewsItemResponse(BaseModel):
    ticker: str
    title: str
    url: Optional[str] = None
    source: Optional[str] = None
    summary: Optional[str] = None
    sentiment: float
    impact_category: str
    confidence: float
    published_at: Optional[str] = None
    fetched_at: str


class EarningsEventResponse(BaseModel):
    ticker: str
    report_date: date
    report_time: Optional[str] = None
    eps_estimate: Optional[float] = None
    eps_actual: Optional[float] = None
    revenue_estimate: Optional[float] = None
    revenue_actual: Optional[float] = None


class EarningsHistoryEventResponse(BaseModel):
    fiscal_quarter: str
    report_date: date
    eps_estimate: Optional[float] = None
    eps_actual: Optional[float] = None
    surprise_pct: Optional[float] = None
    beat: Optional[bool] = None
    next_day_return_pct: Optional[float] = None
    next_day_close_date: Optional[date] = None


class EarningsHistoryResponse(BaseModel):
    ticker: str
    events: list[EarningsHistoryEventResponse] = Field(default_factory=list)


class BalanzImportSkipResponse(BaseModel):
    row_number: int
    ticker: Optional[str] = None
    reason: str


class BalanzImportResponse(BaseModel):
    source_sheet: str
    imported_count: int
    skipped_count: int
    replace_existing: bool
    positions_count_after: int
    imported_symbols: list[str] = Field(default_factory=list)
    skipped_rows: list[BalanzImportSkipResponse] = Field(default_factory=list)


class MarketPulseItemResponse(BaseModel):
    symbol: str
    label: str
    category: str
    price: float
    day_change_pct: float
    relative_to_sma20_pct: Optional[float] = None
    relative_to_sma50_pct: Optional[float] = None
    tone: str
    note: str


class ReliabilityBinResponse(BaseModel):
    bin_lower: float
    bin_upper: float
    sample_size: int
    mean_predicted: float
    fraction_positive: float


class ValidationReportResponse(BaseModel):
    ticker: str
    horizon: str
    warmup: int
    horizon_days: int
    step_days: int
    sample_size: int
    brier_score: float
    reliability_bins: list[ReliabilityBinResponse] = Field(default_factory=list)


class DecisionRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)
    horizon: str = Field(default="short", pattern="^(short|long)$")
    action_taken: str = Field(min_length=1, max_length=32)
    rationale: Optional[str] = Field(default=None, max_length=500)


class DecisionResponse(BaseModel):
    decision_id: int
    ticker: str
    horizon: str
    action_taken: str
    conviction: Optional[float] = None
    rationale: Optional[str] = None
    decided_at: datetime
    realized_return: Optional[float] = None
    realized_at: Optional[datetime] = None
    analysis_snapshot: dict = Field(default_factory=dict)


class MarketOverviewResponse(BaseModel):
    generated_at: datetime
    ticker: Optional[str] = None
    horizon: str
    regime: str
    breadth: str
    summary: str
    warnings: list[str] = Field(default_factory=list)
    instruments: list[MarketPulseItemResponse] = Field(default_factory=list)
