# Multi-Agent Work Queue

## Tracks already completed

### Agent A: Repo Surgeon

- create target structure
- move generated artifacts out of root
- isolate backups and vendor assets

### Agent B: Contracts Agent

- define shared analysis contracts
- make deterministic/probabilistic outputs explicit
- reduce future coupling between backend and frontend

### Agent C: Frontend Agent

- deliver static prototype for landing + analyzer
- validate interaction states before backend integration

## Next parallel wave

### Agent D: Identity Agent

- add login
- add investor profile model
- define personalized risk preferences and local currency defaults
- use local `username + password` auth only in v1
- persist credentials and profile in the app database

### Agent E: Portfolio Agent

- add position model
- add CEDEAR-to-underlying mapping
- compute P&L in ARS and USD
- support manual position entry only in v1
- keep broker-sync boundary abstracted for future adapters

### Agent F: Benchmark Agent

- ingest Argentina inflation
- ingest official and MEP FX series
- ingest CCL FX series
- add `plazo fijo` comparison
- compute real return metrics

### Agent G: API Agent

- expose auth/profile endpoints
- expose portfolio endpoints
- extend analysis payloads with user-aware fields
- keep CEDEAR-first discovery mode for Argentina users

## Following parallel wave

### Agent H: Context Intelligence Agent

- add market regime context
- add macro and news event ingestion
- add catalyst tagging: confirmed / reported / rumored / inferred
- implement rumor-weight policy so weak signals cannot flip a recommendation by themselves

### Agent I: Earnings and Fundamentals Agent

- track upcoming earnings
- track thesis-change and fundamental-change events
- surface changes in guidance, margins, debt and management

### Agent J: Personalization UI Agent

- convert the analyzer into a logged-in workspace
- add portfolio dashboard
- add real-return comparison views
- add user-aware ranking states
- add learning / dictionary surface with glossary and concept tooltips

## Final-stage wave

### Agent K: Social Sentiment Agent

- add X / Reddit / niche community sentiment
- weight social signal as a probabilistic modifier only
- add spam / bot / rumor guardrails

### Agent L: Trading Integration Agent

- define a dedicated trading surface separated from the analysis workspace
- prepare Wallbit API adapter boundary
- add paper-trading and order-confirmation guardrails before any live trading path

## Dependency graph

- Agent D and Agent E define the persistence model needed by G and J.
- Agent F depends on reliable reference-data ingestion and portfolio cost basis rules.
- Agent G depends on D, E and the expanded contracts layer.
- Agent H and Agent I depend on new context schemas and background jobs.
- Agent J depends on D, E, F and G.
- Agent K depends on H and the context-scoring contract.

## Updated definition of done for the next meaningful product milestone

- login and persisted investor profile
- username/password auth without email dependency
- portfolio positions with CEDEAR-aware valuation
- manual position entry
- gains shown in USD and ARS
- inflation / official / MEP / CCL / plazo fijo comparison
- consolidated recommendation card
- deterministic reasons plus external-context reasons
- earnings-aware warnings
- CEDEAR-first landing page
- no hidden backup logic in the main path
