from __future__ import annotations

from dataclasses import dataclass


# Canonical CEDEAR ratios (CEDEARs per 1 underlying US share) sourced from
# BYMA's reference list. These are the source of truth: parity-based
# inference is a last-resort fallback because it snaps to neighbour ratios
# and silently introduces 2-3x errors on tickers like GOOGL/AMZN.
#
# Maintenance: when BYMA announces a CEDEAR split, update the value here and
# add a regression test using a hand-picked local + underlying price pair.
# Last verified: 2026-05 (post Alphabet 20:1 split adjustments).
#
# Tickers we don't yet have a canonical ratio for fall back to parity
# inference + an explicit warning. We never silently use ratio=1.
CANONICAL_CEDEAR_RATIOS: dict[str, float] = {
    # Mega-caps + index
    "AAPL": 10.0,
    "AMZN": 2.0,
    "GOOGL": 58.0,
    "GOOG": 52.0,
    "META": 6.0,
    "MSFT": 5.0,
    "NVDA": 20.0,
    "TSLA": 15.0,
    "QQQ": 18.0,
    "SPY": 20.0,
    "DIA": 20.0,
    "VOO": 12.0,
    "VTI": 8.0,
    # Argentina ADRs (mostly 1:1 because already locally traded as ADR equivalents)
    "GGAL": 10.0,
    "MELI": 10.0,
    "PAM": 25.0,
    "PBR": 4.0,
    "VIST": 1.0,
    "YPF": 1.0,
    # Semis / hardware
    "AMD": 5.0,
    "AVGO": 30.0,
    "INTC": 4.0,
    "TSM": 5.0,
    "ARM": 6.0,
    "MU": 4.0,
    "QCOM": 8.0,
    # AI / cloud / data infra
    "SNOW": 8.0,
    "PLTR": 5.0,
    "CRWD": 24.0,
    "DDOG": 8.0,
    "NET": 4.0,
    "MDB": 16.0,
    "ZS": 16.0,
    "OKTA": 8.0,
    "CRM": 10.0,
    "ORCL": 10.0,
    "ADBE": 20.0,
    # Fintech / consumer tech
    "COIN": 12.0,
    "PYPL": 4.0,
    "SHOP": 5.0,
    "SQ": 4.0,
    "ABNB": 10.0,
    "UBER": 4.0,
    "SPOT": 30.0,
    # Healthcare / pharma
    "ABBV": 8.0,
    "LLY": 30.0,
    "UNH": 30.0,
    # Financials
    "JPM": 12.0,
    "BAC": 4.0,
    "BRK.B": 30.0,
    # Consumer staples / discretionary
    "KO": 5.0,
    "MCD": 20.0,
    "WMT": 5.0,
    "DIS": 6.0,
    # Energy / materials
    "XOM": 5.0,
    "VALE": 1.0,
    # EM / China
    "BABA": 4.0,
    "BIDU": 4.0,
    "JD": 2.0,
    "PDD": 8.0,
    "NU": 1.0,
    # ETFs / sector
    "IBB": 24.0,
    # Brasil
    "ABEV": 1.0,
    # Newer listings
    "ALAB": 4.0,
}


def canonical_cedear_ratio(symbol: str) -> float | None:
    """Return the BYMA-canonical ratio for ``symbol`` or None if unknown."""
    if not symbol:
        return None
    normalized = symbol.strip().upper().replace(".BA", "")
    return CANONICAL_CEDEAR_RATIOS.get(normalized)


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
    """Resolve the CEDEAR ratio with a hard ordering:

    1. ``user_supplied`` — the user explicitly told us the ratio (highest trust).
    2. ``canonical`` — looked up in ``CANONICAL_CEDEAR_RATIOS``. Use this when
       known: parity inference is unreliable for tickers like GOOGL where the
       true ratio (58) is far from a common candidate near observed parity (24).
    3. ``estimated_market_parity`` — derived from live prices. Used when we
       don't have the ticker in the canonical table.
    4. ``fallback_default`` — last resort. Returns ratio=1.0 so the caller
       can still render *something*, but flags it so the UI / valuation
       layer can warn loudly. Never silently trust this value.
    """
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

    # Canonical table is preferred over parity inference. Parity snaps to a
    # neighbour ratio and silently introduces multi-x errors (e.g. GOOGL real
    # ratio is 58, parity often computes ~24 which is a 2.4x error on USD).
    canonical = canonical_cedear_ratio(normalized_symbol) or canonical_cedear_ratio(
        resolved_underlying
    )
    if canonical is not None and canonical > 0:
        return CedearReference(
            symbol=normalized_symbol,
            underlying_ticker=resolved_underlying,
            byma_symbol=byma_symbol,
            cedear_ratio=float(canonical),
            ratio_source="canonical",
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
