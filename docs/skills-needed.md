# Suggested Skills

These are the highest-value skills to add for this repo.

## 1. `timeseries-ml-validation`

Use for:

- walk-forward validation
- leakage prevention
- calibration of probabilities
- confidence reporting

Why:

The current ML-related code mixes heuristics and model outputs without a rigorous validation workflow.

## 2. `quant-backtesting-systems`

Use for:

- event-driven backtests
- position sizing
- transaction-cost modeling
- stop/take-profit simulation

Why:

The current backtesting path is not reliable enough to defend decisions.

## 3. `fastapi-service-design`

Use for:

- typed endpoints
- request/response schemas
- background jobs
- health and cache layers

Why:

You need a clean API layer between engine and UI.

## 4. `frontend-financial-dataviz`

Use for:

- price charts
- indicator overlays
- risk/reward visuals
- compact comparison tables

Why:

The product needs a lot more than generic cards. It needs finance-specific information design.

## 5. `market-data-adapters`

Use for:

- normalizing yfinance and future providers
- retries, cache, rate limits
- event/news/earnings adapters

Why:

The repo now couples analysis directly to raw provider calls.

## 6. `options-strategy-design`

Use for:

- mapping directional views to options ideas
- liquidity and IV filters
- guardrails for unsuitable contracts

Why:

If you want `put opciones`, `covered call` or `cash-secured put`, that needs explicit rules and constraints.

## 7. `repo-refactor-orchestrator`

Use for:

- staged migrations
- legacy freezing
- package splits
- safe moves with compatibility shims

Why:

The repo already has several generations of code mixed together.

## Existing session skills that help now

- `frontend-interaction-states`
- `skill-creator`

If you want, I can use `skill-creator` next to author the missing skills directly in your Codex skills directory.
