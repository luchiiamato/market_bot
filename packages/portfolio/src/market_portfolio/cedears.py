from __future__ import annotations

from dataclasses import dataclass


COMMON_RATIO_CANDIDATES = [
    1,
    2,
    3,
    4,
    5,
    6,
    8,
    10,
    12,
    15,
    18,
    20,
    24,
    25,
    30,
    36,
    40,
    48,
    60,
    72,
    96,
    120,
    144,
]


@dataclass
class CedearReference:
    symbol: str
    underlying_ticker: str
    byma_symbol: str
    cedear_ratio: float
    ratio_source: str


def build_byma_symbol(symbol: str) -> str:
    base_symbol = symbol.strip().upper().replace(".BA", "").replace(".", "")
    return f"{base_symbol}.BA"


def resolve_cedear_reference(
    symbol: str,
    underlying_ticker: str | None,
    user_ratio: float | None,
    current_ccl: float | None,
    local_price_ars: float | None,
    underlying_price_usd: float | None,
) -> CedearReference:
    normalized_symbol = symbol.strip().upper().replace(".BA", "")
    resolved_underlying = (underlying_ticker or normalized_symbol).strip().upper()
    byma_symbol = build_byma_symbol(normalized_symbol)

    if user_ratio is not None and user_ratio > 0:
        return CedearReference(
            symbol=normalized_symbol,
            underlying_ticker=resolved_underlying,
            byma_symbol=byma_symbol,
            cedear_ratio=float(user_ratio),
            ratio_source="user_supplied",
        )

    estimated_ratio = estimate_cedear_ratio(current_ccl, local_price_ars, underlying_price_usd)
    if estimated_ratio is not None:
        return CedearReference(
            symbol=normalized_symbol,
            underlying_ticker=resolved_underlying,
            byma_symbol=byma_symbol,
            cedear_ratio=estimated_ratio,
            ratio_source="estimated_market_parity",
        )

    return CedearReference(
        symbol=normalized_symbol,
        underlying_ticker=resolved_underlying,
        byma_symbol=byma_symbol,
        cedear_ratio=1.0,
        ratio_source="fallback_default",
    )


def estimate_cedear_ratio(
    current_ccl: float | None,
    local_price_ars: float | None,
    underlying_price_usd: float | None,
) -> float | None:
    if not current_ccl or not local_price_ars or not underlying_price_usd:
        return None
    if current_ccl <= 0 or local_price_ars <= 0 or underlying_price_usd <= 0:
        return None

    parity_ratio = (underlying_price_usd * current_ccl) / local_price_ars
    closest = min(COMMON_RATIO_CANDIDATES, key=lambda candidate: abs(candidate - parity_ratio))
    if closest <= 0:
        return None
    relative_error = abs(closest - parity_ratio) / max(parity_ratio, 1e-9)
    if relative_error <= 0.35:
        return float(closest)
    return round(max(1.0, parity_ratio), 2)
