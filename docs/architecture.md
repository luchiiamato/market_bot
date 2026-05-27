# Market Bot Target Architecture

## Goal

Build one product with a single analysis surface that combines:

- deterministic technical analysis
- probabilistic scenario analysis
- actionable suggestion policy
- ranked opportunity discovery on the landing page
- investor profile and portfolio tracking
- Argentina benchmark comparisons
- external context from news, macro and events

## Current salvageable modules

| Current file | Status | Target destination |
| --- | --- | --- |
| `technical.py` | reusable seed | `packages/engine/src/market_bot/indicators/` |
| `ml_prediction.py` | reusable only as temporary heuristic | `packages/engine/src/market_bot/models/heuristics.py` |
| `newmodel/trading_bot.py` | best intraday signal seed | `packages/engine/src/market_bot/signals/intraday.py` |
| `recomendaciones/investment_recommendations.py` | best ranking/scoring seed | `packages/engine/src/market_bot/strategies/ranking.py` |
| `earnings_analysis.py` | useful event-risk seed | `packages/engine/src/market_bot/models/event_risk.py` |

## Freeze candidates

These should not be extended before they are replaced or rewritten:

- `market_analyzer.py`
- `backtesting.py`
- `optimizer.py`
- `quality_filters.py`
- `new_investment.py`
- `perplexity.py`
- `social_analysis.py`
- `tickers.py`

## Product model

### 1. Identity and investor profile

Inputs:

- user account
- investor preferences
- risk profile
- local currency and benchmark defaults

Outputs:

- personalized policy constraints
- profile-aware ranking and action filters

### Authentication decision for v1

- local database-backed `username + password`
- no email confirmation
- no passwordless flow
- no Google OAuth in this phase

### 2. Portfolio and instrument master

Inputs:

- user positions
- instrument type
- CEDEAR mapping
- FX series

Outputs:

- position valuation in ARS and USD
- realized and unrealized P&L
- real-return comparison versus local benchmarks

### Portfolio ingestion decision for v1

- manual position entry only
- future broker sync can be added as an adapter, but is not required now

### 3. Deterministic engine

Inputs:

- OHLCV data
- chosen horizon
- optional event window

Outputs:

- trend regime
- momentum regime
- support/resistance map
- volatility regime
- stop loss / take profit reference
- invalidation text
- rule reasons

### 4. Probabilistic engine

Inputs:

- technical features
- event features
- news/sentiment features
- macro and benchmark features
- historical outcome labels

Outputs:

- bull/base/bear scenario probabilities
- calibrated confidence
- dominant features
- uncertainty flags

### 5. Context intelligence

Inputs:

- news and market events
- earnings calendar
- macro context
- company-level catalysts
- fundamental updates

Outputs:

- confirmed catalyst list
- rumor list with confidence tags
- event-risk warnings
- thesis-change warnings

### Reference benchmark layer

The Argentina benchmark layer should normalize against:

- inflation
- USD official
- USD MEP
- USD CCL
- plazo fijo
- ARS nominal cash path

### 6. Decision policy

Inputs:

- deterministic signal
- probabilistic signal
- horizon
- risk profile
- portfolio exposure
- context intelligence

Outputs:

- `buy`
- `sell`
- `hold`
- `go_long`
- `go_short`
- `long_put`
- `covered_call`
- `cash_secured_put`
- `avoid`

## Horizon split

### Short horizon

- primary frames: `1h`, `4h`, `1d`
- focus: trend continuation, mean reversion, event reaction

### Long horizon

- primary frames: `1d`, `1w`
- focus: regime, structure, quality, event risk, positioning

## Proposed repo structure

```text
apps/web
services/api
services/jobs
packages/engine/src/market_bot
packages/identity
packages/portfolio
packages/reference_data
packages/engine/tests
docs
data/generated
data/reference
legacy
vendor
```

## Delivery sequence

1. Add identity, investor profile and user persistence.
2. Add portfolio tracking and CEDEAR-to-stock mapping.
3. Add Argentina benchmark and FX normalization layer.
4. Expand analysis contracts to include context and user-aware outputs.
5. Add earnings and event-risk ingestion.
6. Add external context intelligence for macro, news and catalysts.
7. Refine probabilistic engine with exogenous features.
8. Expose personalized API surfaces.
9. Expand UI from analyzer into portfolio workspace.
10. Add social sentiment in the final phase.

## Integration notes

- Balanz does not currently have a documented public integration path in this repo plan.
- Keep the broker boundary behind an adapter so a future partner or private integration can be added later without changing portfolio domain logic.
