from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class PositionRecord:
    position_id: int
    user_id: int
    instrument_type: str
    symbol: str
    underlying_ticker: str
    byma_symbol: str | None
    cedear_ratio: float | None
    cedear_ratio_source: str | None
    quantity: float
    purchase_date: date
    purchase_price: float
    purchase_currency: str
    notes: str
    created_at: datetime
    updated_at: datetime


@dataclass
class BenchmarkComparison:
    label: str
    tracked_value_ars: float
    outperformance_ars: float
    outperformance_pct: float


@dataclass
class PositionValuation:
    position_id: int
    instrument_type: str
    symbol: str
    underlying_ticker: str
    byma_symbol: str | None
    cedear_ratio: float | None
    cedear_ratio_source: str | None
    quantity: float
    purchase_date: date
    purchase_price: float
    purchase_currency: str
    user_notes: str
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
    benchmark_comparisons: list[BenchmarkComparison] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class PortfolioSummary:
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
    positions: list[PositionValuation] = field(default_factory=list)
