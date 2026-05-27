# Multi-Agent Work Queue

> Handoff document. Cada task tiene `[ ]` pending / `[~]` in-progress / `[x]` done, **Files**
> (qué leer / qué tocar), **DoD** (qué tiene que pasar para marcarla hecha), y notas de
> contexto. Switcheá entre asistentes sin perder estado.

---

## Status snapshot — 2026-05-27

- **Foundation (Agents A–G)**: ✅ entregada. Auth, portfolio CEDEAR, benchmarks AR, API FastAPI y motor ranking.
- **Active milestone**: cerrar los blockers del Definition of Done.
- **Sprint en curso**: Sprint 1 (catalyst tagging, news, earnings calendar).
- **DoD progress**: 7/11 cumplidos. 4 blockers: catalyst confidence, news/macro context, earnings calendar, personalization UI.
- **Deferred (post-DoD)**: Agent K (social sentiment), Agent L (Wallbit/trading).

Convenciones de paths: todos los paths arrancan en `market_bot/` (no en repo root).

---

## 1 · DONE — Foundation layer

### Agent A · Repo Surgeon ✅
Estructura `/packages/{engine,identity,portfolio,reference_data}` lista, legacy aislado en `/legacy/backups`.

### Agent B · Contracts ✅
`packages/engine/src/market_bot/contracts.py` separa `DeterministicSignal` y `ProbabilisticSignal`; tipos: `Horizon`, `Direction`, `ActionType`, `IndicatorSnapshot`, `ScenarioProbability`, `BacktestSummary`, `ModelValidationSummary`, `Catalyst`, `TickerAnalysis`.

### Agent C · Frontend prototype ✅ (rediseñado)
`apps/web/prototype/{index.html, styles.css, app.js}`. Dark/light theme, segmented sliding indicator, Fraunces + JetBrains Mono + DM Sans. Consume `/auth`, `/portfolio`, `/analyze`, `/rankings`, `/universe`.

### Agent D · Identity ✅
- `packages/identity/src/market_identity/{store.py,service.py,models.py}`.
- PBKDF2-HMAC-SHA256 (120k iter), salt 16B; sessions con `token_hash` SHA256, expiry 30d.
- Tablas `users`, `sessions`.
- API: `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET/PUT /profile`.

### Agent E · Portfolio ✅
- `packages/portfolio/src/market_portfolio/{service.py,cedears.py,models.py}`.
- CEDEAR ratio: user-supplied → inferido por paridad CCL (`resolve_cedear_reference`) → fallback 1.0.
- P&L ARS/USD, real return vs inflación, benchmark vs official/MEP/CCL/plazo fijo.
- Tabla `positions`. API: CRUD `/portfolio/positions`, `GET /portfolio/summary`.

### Agent F · Benchmarks AR ✅
- `packages/reference_data/src/market_reference/benchmarks.py` consume `api.argentinadatos.com`.
- Inflación histórica, FX official/MEP/CCL, plazo fijo (factor geométrico).
- API: `GET /benchmarks/current?from_date=YYYY-MM-DD`.

### Agent G · API surface ✅
- `services/api/{app.py,schemas.py}` FastAPI 0.2.0.
- CORS abierto (`allow_origins=*`), bearer token auth, `cedear_only=true` default en rankings/universe.
- Endpoints: `/health`, `/auth/*`, `/profile`, `/portfolio/*`, `/benchmarks/current`, `/analyze`, `/rankings`, `/universe`.

---

## 2 · ACTIVE SPRINT — Sprint 1 · DoD blockers

> Goal: cerrar los 3 BLOCKERS del Definition of Done que dependen de catalyst
> tagging, news ingestion y earnings calendar. Lo hace **Claude** (sequential)
> porque los 3 tocan `contracts.py`, `service.py` y `app.py` en común.

### 1a · Catalyst confidence schema `[~]`
Tagging de catalysts con confianza (`confirmed | reported | rumored | inferred`) + rumor-weight policy.

**Files**
- `packages/engine/src/market_bot/contracts.py` — agregar `CatalystStatus` enum + campos `status`, `source_url`, `observed_at`.
- `packages/engine/src/market_bot/service.py` — `_build_contextual_notes()` etiqueta cada catalyst con status.
- `packages/engine/src/market_bot/models/baseline.py` — aplicar rumor-weight policy a `ProbabilisticSignal`.
- `services/api/schemas.py` — `CatalystResponse` con los nuevos campos.

**DoD**
- `Catalyst.status` requerido (no nullable).
- Política: un catalyst con `status="rumored"` **no** puede flippear `direction` por sí solo; solo modifica `scenarios[i].probability` ±0.10 max.
- `CatalystResponse` retorna `status`, `source_url`, `observed_at` en `/analyze`.

### 1b · News ingestion adapter `[ ]`
Pipeline mínimo de news para enriquecer catalysts y warnings.

**Files**
- `packages/reference_data/src/market_reference/news.py` (NEW) — adapter + cache.
- `packages/reference_data/src/market_reference/news_store.py` (NEW) — tabla `news_items` y queries.
- `packages/reference_data/src/market_reference/__init__.py` — export.
- `services/api/app.py` — `GET /news/{ticker}`.
- `services/api/schemas.py` — `NewsItemResponse`.

**DoD**
- Adapter con `fetch_news(ticker)` que devuelve list[`NewsItem(title, url, source, published_at, sentiment, impact_category, confidence)`].
- Backends posibles: yfinance news (gratis, sin API key) como default + adapter Marketaux opcional via `MARKETAUX_API_KEY`.
- Cache stale-while-revalidate de 2h en tabla `news_items` con `fetched_at`.
- Endpoint `GET /news/{ticker}` (auth required) devuelve últimas N noticias.
- Integración en `_build_contextual_notes`: news <48h con `confidence>=0.6` se agregan como catalyst con `status="reported"`.

### 1c · Earnings calendar `[ ]`
Calendario futuro de earnings + auto-warning si holdings tienen earnings cerca.

**Files**
- `packages/reference_data/src/market_reference/earnings.py` (NEW).
- `packages/reference_data/src/market_reference/earnings_store.py` (NEW) — tabla `earnings_calendar`.
- `services/api/app.py` — `GET /earnings/upcoming`.
- `packages/portfolio/src/market_portfolio/service.py` — usa earnings store para auto-warning.

**DoD**
- Tabla `earnings_calendar(ticker, report_date, eps_estimate, eps_actual, revenue_estimate, revenue_actual, fetched_at)`.
- Sync function `sync_earnings_for_tickers(tickers)` que pulla via yfinance `Ticker.calendar` y persiste.
- Endpoint `GET /earnings/upcoming` (auth) filtrado a holdings del usuario + tickers en universe.
- Portfolio: si `holding.earnings_date <= today + 7d` y `user.risk_tolerance == "low"` → guardrail `"Earnings en N días: el gap risk puede borrar la tesis técnica."`.

---

## 3 · NEXT — Sprint 2 · Personalization workspace

> Goal: cerrar Agent J. Reusar el prototype, no rewrite. Codex y Claude pueden
> paralelizar (2a vs 2b/2c no comparten archivos).

### 2a · Ranking user-aware `[ ]` — **owner: backend agent**
Filtrar `/rankings` por perfil del usuario y añadir "why for you".

**Files**
- `packages/engine/src/market_bot/service.py` — `rank_universe(profile_filters: ...)`.
- `packages/engine/src/market_bot/strategies/policy.py` — penalty por vol/drawdown según `risk_tolerance`.
- `services/api/app.py` — `/rankings` acepta auth opcional y aplica filtros del perfil del usuario logueado.
- `services/api/schemas.py` — `RankingItemResponse` agrega `why_for_you: list[str]`.

**DoD**
- `risk_tolerance=low` filtra tickers con `realized_vol > 0.04` o catalyst `rumored` que invertiría el verdict.
- `risk_tolerance=high` no filtra, pero re-ranquea favoreciendo `probabilistic.confidence > 0.7`.
- `investor_profile=conservative` excluye acciones `GO_SHORT`, `LONG_PUT`.
- Cada item del ranking incluye `why_for_you` con 1-3 razones legibles ("matches aggressive profile", "earnings in 18d", etc.).

### 2b · Workspace logged-in frontend `[ ]` — **owner: frontend agent**
Reordenar el prototype: holdings primero, ranking filtrado segundo, learning tercero.

**Files**
- `apps/web/prototype/index.html` — reorder `surface-stack` workspace: portfolio panel **primero**, radar segundo, verdict tercero (verdict aparece on-demand).
- `apps/web/prototype/app.js` — al login, autoload portfolio + rankings con auth header.
- `apps/web/prototype/styles.css` — estilo del catalyst status chip y "why for you" pill.

**DoD**
- Usuario logueado ve sus holdings sin tener que tocar nada.
- Radar muestra `why_for_you` debajo del ticker.
- Verdict panel solo aparece si el usuario hace click en analizar.
- Catalyst chips muestran color según `status`: confirmed=citrus, reported=paper, rumored=neutral con outline dashed, inferred=ghost.

### 2c · Real-return comparison render `[ ]` — **owner: frontend agent**
UI para `/portfolio/summary` que ya devuelve `benchmark_comparisons`.

**Files**
- `apps/web/prototype/app.js` — función `renderBenchmarkBars(summary)`.
- `apps/web/prototype/styles.css` — `.benchmark-bar`, `.benchmark-bar-fill`.
- `apps/web/prototype/index.html` — sección `<section class="panel benchmark-panel">` en workspace.

**DoD**
- Barras horizontales lado-a-lado: TU portfolio vs MEP vs CCL vs Oficial vs Inflación vs Plazo fijo.
- Cada barra muestra ARS-valor y outperformance %.
- Color rule: bull si outperformance > 0, bear si < 0.
- Responsive: en mobile colapsa a stack vertical.

---

## 4 · NEXT — Sprint 3 · Validation, audit, observability

> Goal: validar que el motor funciona y dejar bases para producción. Tasks
> 3a/3b/3d son independientes — paralelizables. 3c toca `app.py` (esperar a
> Sprint 2 si hay cambios pendientes en `app.py`).

### 3a · Decision audit log `[ ]`
Trackear las decisiones del usuario contra snapshots del análisis.

**Files**
- `packages/identity/src/market_identity/decisions.py` (NEW) — `DecisionLog` + store.
- `packages/identity/src/market_identity/store.py` — tabla `user_decisions`.
- `services/api/app.py` — `POST /decisions`, `GET /decisions`.
- `services/api/schemas.py` — `DecisionRequest`, `DecisionResponse`.

**DoD**
- Tabla `user_decisions(id, user_id, ticker, action_taken, analysis_snapshot_json, decided_at)`.
- `POST /decisions` recibe `{ticker, action, analysis_id?}` y persiste el snapshot completo del análisis.
- `GET /decisions?since=YYYY-MM-DD` lista las decisiones del usuario.
- (Stretch) job que después de 30d corre el motor de nuevo y guarda `realized_return` para calibrar.

### 3b · Validation endpoint con Brier score `[ ]`
Métricas históricas de calibración del modelo probabilístico.

**Files**
- `packages/engine/src/market_bot/validation/` (NEW) — `brier.py`, `reliability.py`.
- `packages/engine/src/market_bot/service.py` — `validate_ticker(ticker, lookback_days)`.
- `services/api/app.py` — `GET /validation/{ticker}`.
- `services/api/schemas.py` — `ValidationReportResponse`.

**DoD**
- Walk-forward: por cada día en `lookback_days`, generar señal probabilística, comparar contra return realizado.
- Brier score por ticker; reliability bins (10 buckets).
- Endpoint devuelve `{ticker, lookback_days, brier_score, reliability_bins, sample_size}`.
- Sin tests = no PR.

### 3c · Rate limiting + structured logging `[ ]`
Producción-ready basics.

**Files**
- `services/api/app.py` — `slowapi` en `/auth/*` y `/analyze`.
- `services/api/logging_config.py` (NEW) — JSON formatter, request ID middleware.
- `requirements.txt` — agregar `slowapi>=0.1.9`.

**DoD**
- `/auth/login` rate-limited a 5 / 15min / IP. `/auth/register` a 3 / hora / IP. `/analyze` a 30 / min / IP.
- Cada response loggea `{request_id, route, status, latency_ms, user_id?}` en JSON.
- Errores no exponen stacktrace al cliente.

### 3d · Critical tests `[ ]`
Suite mínima para que cambios futuros no rompan en silencio.

**Files**
- `tests/test_auth_flow.py` — register → login → /profile → logout.
- `tests/test_cedear_ratio.py` — `resolve_cedear_reference` con casos: user-supplied, parity match, parity miss, fallback.
- `tests/test_benchmarks.py` — `ArgentinaBenchmarkService` con HTTP mocked (`responses` o `requests-mock`).
- `tests/test_engine_golden.py` — análisis golden file para 3 tickers (AAPL, MELI, YPF) con OHLC fixture.
- `tests/conftest.py` — fixture DB temporal, mock yfinance.
- `requirements-dev.txt` (NEW) — `pytest`, `pytest-asyncio`, `requests-mock`, `httpx`.

**DoD**
- `pytest tests/` corre en <30s sin internet.
- Cobertura mínima 60% en `packages/identity` y `packages/portfolio`.

---

## 5 · DEFERRED — Backlog post-DoD

### Agent K · Social Sentiment `[deferred]`
**Rationale**: signal-to-noise demasiado bajo para el stage actual. Antes de invertir acá, validar que el motor predice bien (Sprint 3b) y que los usuarios usan las recomendaciones (Sprint 3a).

### Agent L · Trading Integration / Wallbit `[blocked]`
**Bloqueado por**: 3b (validación del motor) + paper trading sandbox + auditoría de órdenes. No tocar antes de tener Brier histórico.

### Mejoras técnicas pendientes (backlog técnico)
- SQLite WAL mode (`PRAGMA journal_mode=WAL`) para concurrencia en `/analyze` paralelo.
- Alembic migrations en vez de raw `CREATE TABLE IF NOT EXISTS` (cuando schema cambie >2 veces).
- Refresh tokens 24h en vez de access tokens 30d.
- Tabla canónica `cedear_ratios` (fuente BYMA) — la inferencia por paridad debería ser fallback.
- `API_BASE_URL` env var en frontend para deploy split.
- yfinance OHLC cache diferenciado por trading-hours vs after-hours.

---

## 6 · Definition of Done (milestone actual)

| Requisito | Status |
|---|---|
| login + persisted investor profile | ✅ |
| username/password sin email | ✅ |
| portfolio CEDEAR-aware valuation | ✅ |
| manual position entry | ✅ |
| gains en USD y ARS | ✅ |
| inflation / official / MEP / CCL / plazo fijo comparison | ✅ (data) / ⚠️ (UI render → Sprint 2c) |
| consolidated recommendation card | ✅ |
| deterministic + external-context reasons | ⚠️ (context falta → Sprint 1b) |
| earnings-aware warnings | ❌ → Sprint 1c |
| CEDEAR-first landing | ✅ |
| no hidden backup logic in main path | ✅ |
| **catalyst confidence tagging** (implicit blocker) | ❌ → Sprint 1a |
| **personalized workspace** (Agent J) | ❌ → Sprint 2 |

---

## 7 · Dependency graph (actualizado)

```
Sprint 1a (catalyst schema) ──► Sprint 2a (ranking filters)
Sprint 1b (news)            ──► Sprint 2a (uses news as catalyst input)
Sprint 1c (earnings)        ──► Sprint 2a (filters tickers con earnings <7d)
Sprint 2a + 2b + 2c         ──► (Agent J complete)
Sprint 3a (audit log)        ──► (validación humana del motor)
Sprint 3b (Brier)            ──► Agent L (unblock trading)
Sprint 3c (rate limit/logs) ──► deploy prod
Sprint 3d (tests)            ──► all of the above (safety net)
```

---

## 8 · Handoff protocol

Cuando vos (Codex / Claude / human) terminés una task:

1. Cambiá su checkbox a `[x]`.
2. Apendá una línea `> ✅ DONE 2026-MM-DD por <agent>: <PR/commit ref si aplica>`.
3. Si destrabaste algo, movelo de "blocked" a `[ ]` en la sección correspondiente.
4. Si encontraste un blocker nuevo, registralo en la sección 5 (backlog técnico) o como nueva task del sprint correspondiente.
5. No empieces a trabajar en `[~]` si no estás seguro de que el otro asistente lo soltó — preguntá al usuario.
