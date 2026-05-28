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
    # NEW (Sprint 7.2): return vs the user's preferred FX benchmark (MEP/CCL/Oficial).
    # `real_return_pct` is canonical "vs inflación" — we keep it as the textbook
    # definition. This second field answers "did I beat the dollar I chose as
    # reference?" — the question most Argentinian retail investors actually want
    # answered. Both labels are surfaced in the UI side-by-side.
    preferred_benchmark_return_pct: float = 0.0
    preferred_benchmark_label: str = "inflation"
    benchmark_comparisons: list[BenchmarkComparison] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class ExposureBucket:
    """One slice of the portfolio grouped by sector or region.

    ``pct`` is normalized 0–1 (not 0–100) so the frontend can multiply by 100
    when rendering and skip a unit-conversion footgun.
    """

    label: str
    total_value_ars: float
    pct: float


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
    # NEW (Sprint 7.2): aggregate vs preferred benchmark across positions.
    total_preferred_benchmark_return_pct: float = 0.0
    preferred_benchmark_label: str = "inflation"
    positions: list[PositionValuation] = field(default_factory=list)
    # NEW: where is the portfolio concentrated? Sector and region buckets are
    # computed once at summary time so the UI doesn't have to re-aggregate.
    sector_exposure: list[ExposureBucket] = field(default_factory=list)
    region_exposure: list[ExposureBucket] = field(default_factory=list)
