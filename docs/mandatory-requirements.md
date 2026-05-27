# Mandatory Product Requirements

These requirements override the earlier "single ticker analyzer" scope and become mandatory for the product roadmap.

## Scope Rule

- The product is no longer just an analyzer.
- It becomes a personalized investment workspace for Argentina-based users.
- Default local currency is `ARS`.
- The landing page should still prioritize CEDEAR-compatible ideas for Argentine users.

## Requirement 1. Login and Investor Profile

The app must support user login and a persisted investor profile.

### Current product decision

- v1 auth will use `username + password`
- credentials are stored in the product database
- no email flow is required in this phase
- no passwordless or OAuth flow is required in this phase
- future target can include Google login, but it is explicitly out of scope now

### Minimum profile fields

- full name or display name
- username
- local currency: `ARS` by default
- investor profile: `conservative`, `moderate`, `aggressive`
- preferred horizon: `short`, `long`, `mixed`
- preferred instrument types: `cedear`, `stock`, `both`
- risk tolerance
- benchmark preference for real-return comparisons

### Product rule

- Action suggestions must be filtered or ranked against the investor profile.
- A conservative profile should not receive the same default action stack as an aggressive profile.

## Requirement 2. Portfolio and CEDEAR/Stock Position Tracking

Each user must be able to register their own positions.

### Current product decision

- portfolio loading is manual in v1
- broker sync is out of scope unless a documented broker integration is available later

### Position fields

- instrument type: `cedear` or `stock`
- local symbol entered by the user
- underlying ticker
- CEDEAR ratio if applicable
- quantity
- purchase date
- purchase price
- purchase currency
- optional notes

### Mandatory calculations

- current market value
- unrealized P&L in `USD`
- unrealized P&L in `ARS`
- return percentage
- average cost
- exposure by ticker, sector and currency

### CEDEAR-specific rule

If the user selects `cedear`, the system must:

- resolve the CEDEAR instrument itself
- resolve the underlying stock
- map the CEDEAR-to-stock ratio
- use the CEDEAR market price for the position valuation
- preserve the relation to the underlying stock for analysis and news context

## Requirement 3. External Market and News Context

The system must not analyze only price and technical values.

It must also analyze external factors that can affect the asset:

- market regime
- macro shocks
- geopolitical events
- regulations
- sector-specific restrictions
- crypto contagion when relevant
- large market moves that can spill into the analyzed asset

### Product rule

Every recommendation should show:

- what comes from technical analysis
- what comes from external context
- whether the external signal is confirmed, reported or still a rumor

## Requirement 4. Commercial Contracts, Listings and Index Inclusion Catalysts

The system must evaluate corporate catalysts such as:

- important commercial contracts signed
- contracts reportedly close to being signed
- IPO or listing-related developments
- index inclusion or possible inclusion narratives
- strategic partnerships

### Confidence model

Catalysts must be tagged with one of these statuses:

- `confirmed`
- `reported`
- `rumored`
- `inferred`

Rumors can influence confidence, but must never be presented as hard facts.

## Requirement 5. Upcoming Earnings

The system must track future earnings and event windows.

### Mandatory outputs

- next earnings date
- days until earnings
- event-risk warning
- whether the recommendation should be downgraded because of earnings proximity

## Requirement 6. Changes in Investment Fundamentals

The system must evaluate whether the company changed the fundamentals behind the investment thesis.

### Minimum fundamental change categories

- revenue growth trend
- margins and profitability trend
- debt or liquidity deterioration
- guidance changes
- management changes
- capex / product roadmap changes
- regulatory or legal changes

### Product rule

The analyzer should surface not only "what price is doing" but also "whether the original thesis is still intact."

## Requirement 7. Argentina Real-Return Benchmarking

The platform must compare nominal gains against Argentina-specific erosion and alternatives.

### Mandatory benchmark series

- Argentina inflation
- official USD exchange rate
- MEP exchange rate
- CCL exchange rate
- ARS cash reference
- fixed-term deposit benchmark (`plazo fijo`)

### Mandatory outputs

- nominal return in `ARS`
- nominal return in `USD`
- inflation-adjusted real return
- return measured against official USD and MEP paths
- comparison against a stable local benchmark such as `plazo fijo`

### Product rule

A position should be able to show:

- "you beat inflation by X"
- "you beat MEP dollar by Y"
- "you beat plazo fijo by Z"

## Requirement 8. Social Sentiment Analysis

This is mandatory for the final stage, but not a blocker for the next build wave.

### Target sources

- X / Twitter
- Reddit
- niche investing blogs or communities

### Usage rule

Social sentiment must be a probabilistic modifier, not the primary decision engine.

### Minimum safeguards

- source attribution
- spam / bot resistance
- separation between hype and confirmed information
- decayed weighting over time

## Current Policy Decisions

### Rumor policy

The system will use a four-level external-information policy:

- `confirmed`: official filing, official company statement, regulator, exchange or similarly primary source
- `reported`: established media or specialized source citing identifiable evidence
- `rumored`: market chatter, non-primary sources or weakly sourced discussion
- `inferred`: conclusion produced by the model from several weaker signals

#### Scoring rule

- `confirmed` can directly affect recommendation confidence
- `reported` can moderately affect recommendation confidence
- `rumored` can only act as a weak modifier and must always be visually labeled
- `inferred` can create a watch item, but should not flip the recommendation on its own

#### UI rule

- rumors and inferred items must never appear in the same visual style as confirmed catalysts
- the user must always be able to see why an item is not treated as a fact

### Broker-integration policy

- Balanz sync is not part of v1
- as of `2026-05-27`, no documented public or partner API was confirmed in the official Balanz domains reviewed for this planning pass
- unless Balanz later exposes a documented public or partner API, positions remain manual

## Cross-Cutting Requirements

### Learning surface

The product must include a user-facing learning or dictionary surface.

Minimum expectations:

- a glossary of indicators and product concepts
- quick explanations on hover or focus for key indicators
- a persistent section where the user can read the concepts in one place

### Traceability

Every important recommendation should explain:

- which inputs were used
- which signals were deterministic
- which signals were probabilistic
- which signals came from external news or macro context

### Personalization

Portfolio state and investor profile must affect rankings, not only single-ticker analysis.

### Argentina-first defaults

- local currency defaults to `ARS`
- CEDEAR-aware discovery is the default landing mode
- local benchmark comparisons are mandatory in portfolio views

## Architecture Impact

These requirements imply five product domains:

1. identity and investor profile
2. portfolio and CEDEAR mapping
3. market + macro + news context intelligence
4. benchmark and FX normalization for Argentina
5. sentiment intelligence for the final phase
6. learning and explainability surface for the user

## Delivery Phasing

### Next wave mandatory

- login
- investor profile
- portfolio positions
- CEDEAR mapping
- earnings tracking
- Argentina benchmark layer

### Following wave mandatory

- market regime + external news context
- contract / partnership / listing catalyst tracking
- fundamental thesis change detection

### Final-stage mandatory

- social sentiment from X / Reddit / specialized communities

## Acceptance Standard

No feature in this document is considered complete unless:

- data is persisted per user
- the UI shows the output clearly
- the source of the signal is visible
- the signal affects either recommendations, portfolio analytics or both
