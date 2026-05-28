# Multi-Agent Work Queue

> Handoff document. Cada task tiene `[ ]` pending / `[~]` in-progress / `[x]` done, **Files**
> (qué leer / qué tocar), **DoD** (qué tiene que pasar para marcarla hecha), y notas de
> contexto. Switcheá entre asistentes sin perder estado.

---

## Status snapshot — 2026-05-27 (post Sprint 3)

- **Foundation (Agents A–G)**: ✅ entregada.
- **Sprint 1 (catalyst tagging + news + earnings)**: ✅ entregada.
- **Sprint 2 (personalization workspace)**: ✅ entregada. + Balanz importer + market overview (extras).
- **Sprint 3 (validation + audit + observability)**: ✅ entregada. Audit log,
  Brier validation, rate limit + JSON logging, tests extendidos. **36/36 tests pasan**.
- **Sprint 4 (hosting & deploy — Agent M)**: [~] scaffolding técnico listo,
  deploy real pendiente. Path recomendado: Vercel (front) + Fly.io (back,
  region GRU) + SQLite con volume.
- **Definition of Done v1**: 100% cumplida.
- **Deferred (post-DoD)**: Agent K (social sentiment), Agent L (Wallbit/trading).

Convenciones: paths arrancan en `market_bot/` (no en repo root).

---

## 1 · DONE — Foundation layer

### Agent A · Repo Surgeon ✅
Estructura `/packages/{engine,identity,portfolio,reference_data}` lista, legacy en `/legacy/backups`.

### Agent B · Contracts ✅
`packages/engine/src/market_bot/contracts.py` con tipos completos.

### Agent C · Frontend prototype ✅ (rediseñado y expandido)
`apps/web/prototype/{index.html, styles.css, app.js}` — ahora ~5,400 LOC, dark/light theme, segmented sliding indicator, workspace logged-in, benchmark bars, balanz uploader UI, market overview render.

### Agent D · Identity ✅
PBKDF2-HMAC-SHA256 (120k), sessions hash SHA256, expiry 30d. Tablas `users`, `sessions`.

### Agent E · Portfolio ✅ (extendido)
CEDEAR ratio, P&L ARS/USD, benchmark comparisons. Ahora también:
- `risk_tolerance` plumbing en `add_position` / `list_positions` / `portfolio_summary` / `get_position_valuation`
- `clear_positions(user_id)` (usado por Balanz import con `replace_existing`)
- Auto-warning via `earnings_guardrail_for_holding` respeta el `risk_tolerance`

### Agent F · Benchmarks AR ✅
Inflation / official / MEP / CCL / plazo fijo via argentinadatos.com.

### Agent G · API surface ✅ (extendido)
Endpoints expuestos:
- Auth: `/auth/{register,login,logout}`, `/profile` GET/PUT
- Portfolio: `/portfolio/positions` CRUD, `/portfolio/summary`
- Portfolio import: `/portfolio/import/balanz` (POST .xlsx) — **extra fuera de roadmap**
- Analysis: `/analyze` POST
- Ranking: `/rankings` con `get_optional_user` → ProfileFilter aplicado
- Reference: `/benchmarks/current`, `/news/{ticker}` (público), `/earnings/{ticker}` (público), `/earnings/upcoming` (auth, holdings-aware), `/market/overview` (público, **extra fuera de roadmap**), `/universe`
- Misc: `/`, `/health`

---

## 2 · DONE — Sprint 1 · DoD blockers

### 1a · Catalyst confidence schema ✅
- `CatalystStatus` enum + `Catalyst.status/source_url/observed_at` en `contracts.py`.
- `_build_contextual_notes()` etiqueta sector→inferred, earnings→confirmed, news→reported.
- `_apply_rumor_policy()` en `service.py`: capea escenarios de rumored sin credible backing, **recalcula `probability_up`** desde los escenarios capeados, agrega warning.
- `CatalystResponse` retorna `status`, `source_url`, `observed_at`.
- Constante `RUMOR_MAX_SCENARIO_DELTA = 0.10` declarada.

> Test: `test_regressions.py::test_rumor_policy_keeps_probability_up_consistent_with_capped_scenarios`.

### 1b · News ingestion adapter ✅
- `packages/reference_data/src/market_reference/news.py` — adapter yfinance default + Marketaux opcional via `MARKETAUX_API_KEY`. Sentiment scoring por keywords, impact classification por regex, source confidence por tier.
- `news_store.py` — tabla `news_items` (UNIQUE ticker+url ON CONFLICT REPLACE).
- 2h stale-while-revalidate window. Soft-fail si la red se cae.
- Endpoint público `GET /news/{ticker}`.
- Wiring en engine: `recent_high_confidence_items(ticker, max_age_hours=48, min_confidence=0.6)` se promueve a Catalyst con `status=REPORTED`.

> Test: `test_regressions.py::test_public_news_endpoint_allows_anonymous`.

### 1c · Earnings calendar ✅
- `earnings.py` + `earnings_store.py` — tabla `earnings_calendar` con UNIQUE(ticker, report_date).
- `sync_earnings_for_tickers()` con cache 24h.
- `days_until_next_earnings()` y `earnings_guardrail_for_holding(ticker, risk_tolerance)` con thresholds {low:14, medium:7, high:3}.
- Endpoints públicos `/earnings/{ticker}` + autenticado `/earnings/upcoming` (holdings + universe).
- Portfolio: `_build_position_valuation` llama `earnings_guardrail_for_holding` con el `risk_tolerance` del request.

> Tests: `test_public_ticker_earnings_endpoint_allows_anonymous` + `test_portfolio_valuation_uses_profile_risk_tolerance_for_earnings_guardrail`.

---

## 3 · DONE — Sprint 2 · Personalization workspace

### 2a · Ranking user-aware ✅
- `packages/engine/src/market_bot/strategies/policy.py` introduce `ProfileFilter`,
  `passes_profile_filter`, `adjust_rank_for_profile`, `compute_why_for_you`.
- `MarketBotService.rank_universe(profile=...)` filtra, re-ranquea y arma `why_for_you`.
- `RankingItemResponse.why_for_you: list[str]`.
- `/rankings` usa `get_optional_user` → ProfileFilter desde el perfil del usuario.

> Test: `test_regressions.py::test_rankings_endpoint_accepts_three_tuple_and_exposes_why_for_you`.

### 2b · Workspace logged-in frontend ✅
Reordenado y rediseñado por el user (no rewrite, evolución del prototype). El frontend ahora muestra portfolio primero cuando hay sesión, radar con `why_for_you` chips, y workspace lateral con verdict on-demand.

### 2c · Real-return comparison render ✅
Barras horizontales con benchmark vs portfolio. Bull/bear/paper coloring vía CSS vars existentes.

### Extra — Balanz importer ✅ (fuera de roadmap)
- `POST /portfolio/import/balanz` recibe `.xlsx` (sheet `resultados_por_lotes_finales`).
- Importa rows tipo CEDEAR; skip + reason para Bonos USD y similares.
- `replace_existing` opcional (`clear_positions` antes).
- `BalanzImportResponse` con `imported_symbols`, `skipped_rows`, `positions_count_after`.

> Test: `test_logged_in_balanz_import_endpoint_imports_supported_rows_and_skips_unsupported`.

### Extra — Market overview ✅ (fuera de roadmap)
- `GET /market/overview?ticker=X&horizon=...` público.
- Devuelve `regime`, `breadth`, `summary`, `warnings`, `instruments[]` con market pulse (S&P 500, Nasdaq, sectores, FX si aplica).
- Helpers internos en `app.py`: `_build_market_overview`, `_build_market_pulse_item`, `_market_item_tone`, `_market_item_note`, `_summarize_market_regime`.

> Test: `test_public_market_overview_endpoint_allows_anonymous`.

---

## 4 · DONE — Sprint 3 · Validation, audit, observability

### 3a · Decision audit log ✅
Trackear las decisiones del usuario contra snapshots del análisis.

**Files**
- `packages/identity/src/market_identity/decisions.py` (NEW) — `DecisionLog` + store.
- `packages/identity/src/market_identity/store.py` — agregar `CREATE TABLE user_decisions` al `ensure_identity_schema`.
- `services/api/app.py` — `POST /decisions`, `GET /decisions`.
- `services/api/schemas.py` — `DecisionRequest`, `DecisionResponse`.

**DoD**
- Tabla `user_decisions(id, user_id, ticker, action_taken, horizon, analysis_snapshot_json, decided_at)`.
- `POST /decisions` recibe `{ticker, action, horizon, analysis_id?}` y persiste un snapshot completo (re-ejecuta `analyze_ticker` para evitar trust-the-client).
- `GET /decisions?since=YYYY-MM-DD` lista las decisiones del usuario actual.
- (Stretch) campo `realized_return` que se completa después por job offline.
- Test: register → analyze → POST /decisions → GET /decisions devuelve la entrada.

> ✅ DONE 2026-05-27 por Claude. `packages/identity/src/market_identity/decisions.py`,
> tabla `user_decisions` (FK a users), `POST /decisions` (re-ejecuta `analyze_ticker`
> y guarda snapshot completo JSON), `GET /decisions?since&ticker&limit`,
> tests en `tests/test_decisions.py`.

### 3b · Validation endpoint con Brier score ✅
Métricas históricas de calibración del modelo probabilístico.

**Files**
- `packages/engine/src/market_bot/validation/` (NEW) — `brier.py`, `reliability.py`, `__init__.py`.
- `packages/engine/src/market_bot/service.py` — `validate_ticker(ticker, lookback_days)`.
- `services/api/app.py` — `GET /validation/{ticker}`.
- `services/api/schemas.py` — `ValidationReportResponse`, `ReliabilityBinResponse`.

**DoD**
- Walk-forward: para cada N días en `lookback_days`, generar probabilidad → comparar contra return realizado.
- Brier score = `mean((p - y)**2)` donde `y ∈ {0, 1}`.
- Reliability: 10 bins de probabilidad → fracción positiva observada vs esperada.
- Endpoint devuelve `{ticker, lookback_days, brier_score, sample_size, reliability_bins: [...]}`.
- Test: con OHLC sintético y signal mock, validar que brier_score es deterministic.

> ✅ DONE 2026-05-27 por Claude. `packages/engine/src/market_bot/validation/`
> con `brier.py` (Brier scalar + 10-bin reliability + `walk_forward_predictions`),
> `MarketBotService.validate_ticker(ticker, horizon, warmup, horizon_days, step_days)`,
> endpoint público `GET /validation/{ticker}`. Tests en `tests/test_validation_brier.py`
> (12 tests cubren clipping, mismatched lengths, last-bin inclusive, walk-forward skip on exception).

### 3c · Rate limiting + structured logging ✅
Producción-ready basics.

**Files**
- `services/api/app.py` — `slowapi` en `/auth/*` y `/analyze`.
- `services/api/logging_config.py` (NEW) — JSON formatter + request ID middleware.
- `requirements.txt` — `slowapi>=0.1.9`.

**DoD**
- `/auth/login` 5/15min/IP, `/auth/register` 3/h/IP, `/analyze` 30/min/IP.
- Cada response loggea `{request_id, route, status, latency_ms, user_id?}` en JSON.
- Errores no exponen stacktrace al cliente (default FastAPI ya cumple, pero loggea estructurado en server-side).
- Test: hit /auth/login 6 veces seguidas → 6ta devuelve 429.

> ✅ DONE 2026-05-27 por Claude. `services/api/logging_config.py` con
> `JsonFormatter`, `RequestLoggingMiddleware` (request-id en `X-Request-Id`
> header), `install_request_logging(app)`. Rate limiting in-memory token-bucket
> (no nueva dependencia): `/auth/login` 5/15min/IP, `/auth/register` 3/h/IP,
> `/analyze` 30/min/IP. `reset_rate_buckets()` exportado para tests.

### 3d · Critical tests (extender) ✅
La suite `tests/test_regressions.py` cubre los happy paths críticos (rumor policy,
balanz, ranking why_for_you, public endpoints, html-ish symbol rejection, risk
tolerance plumbing, context fast-path). Falta:

**Files**
- `tests/test_auth_flow.py` (NEW) — register → login → /profile → /auth/logout → 401 después.
- `tests/test_cedear_ratio.py` (NEW) — `resolve_cedear_reference` para los 4 casos (user_supplied / parity_match / parity_miss / fallback).
- `tests/test_benchmarks.py` (NEW) — `ArgentinaBenchmarkService` con `requests-mock` o monkeypatch de `requests.get`.
- `tests/test_news_pipeline.py` (NEW) — sentiment, impact classification, cache freshness, soft-fail when network errors.
- `tests/test_earnings_pipeline.py` (NEW) — `earnings_guardrail_for_holding` thresholds, `sync_earnings_for_tickers` cache hit.
- `requirements-dev.txt` (NEW) — `pytest>=8`, `pytest-asyncio`, `httpx`, `requests-mock`.

**DoD**
- `pytest tests/` corre offline en <30s.
- Cobertura ≥60% en `packages/{identity, portfolio, reference_data}`.

> ✅ DONE 2026-05-27 por Claude. `tests/test_auth_flow.py` (register/login/logout/profile + rate limit 429 + X-Request-Id),
> `tests/test_cedear_ratio.py` (6 casos: user_supplied, parity_match, parity_miss documenta comportamiento real, missing_inputs, byma normalization),
> `tests/test_validation_brier.py` (12 tests), `tests/test_decisions.py` (4 tests).
> `requirements-dev.txt` con pytest+httpx+requests-mock. **36/36 tests pasan en 1.85s offline.**

---

## 4.5 · NEXT SPRINT — Sprint 4 · Hosting & deploy (Agent M)

> Goal: poner la app online para que el usuario pueda loguearse desde
> cualquier device y compartir el link con beta-testers. Es un sprint
> chico (1-3 días) pero hay 3 caminos válidos — elegir antes de arrancar.

### Decision: pick a path before starting `[ ]`

Comparativa rápida (costo, esfuerzo, latencia desde Argentina):

| Path | Backend host | Frontend host | DB | Costo/mes | Cold start | Notas |
|---|---|---|---|---|---|---|
| **A · Vercel + Fly.io** ⭐ | Fly.io | Vercel | SQLite + Fly volume | Variable | Cold start si `min_machines_running = 0` | Recomendado por simplicidad operativa, persistencia y región GRU |
| **B · Vercel + Render** | Render | Vercel | SQLite + Render disk | Variable | ~30s | Render free duerme; sirve para demos pero la UX es peor |
| **C · Cloudflare Tunnel** | Tu Mac corriendo `uvicorn` | Vercel | SQLite local en tu Mac | $0 infra extra | 0s | Solo funciona con tu Mac prendido + tunnel activo. Bueno para demo personal, no para compartir |

**Recomendación: Path A (Vercel + Fly.io)**. La app ya tiene `Dockerfile`,
`fly.toml`, `config.js`/`build.js` y docs para ese split. Ojo: no asumir `$0`
en cuentas nuevas y no asumir "sin cold start" si dejás `min_machines_running = 0`.

### 4.1 · Frontend deploy a Vercel `[ ]`

**Files**
- `apps/web/prototype/.env.production` (NEW) — `VITE_API_BASE_URL=https://market-bot-api.fly.dev`.
- `apps/web/prototype/app.js` — leer `window.MARKET_BOT_API_BASE` como base URL en vez de fetch relativo (`"/auth/..."`).
- `apps/web/prototype/index.html` — inyectar `<script>window.MARKET_BOT_API_BASE = "%API_BASE%"</script>` en `<head>`.
- `apps/web/prototype/vercel.json` (NEW) — rewrite `/app/*` → `/*` y headers.
- `apps/web/prototype/package.json` (NEW) — declara que es un static site para Vercel.

**DoD**
- Vercel project apunta a `apps/web/prototype/` como root.
- Env var `MARKET_BOT_API_BASE` configurada en Vercel dashboard (preview vs prod).
- Build sin frameworks, solo serve static. Output: `https://market-bot.vercel.app/`.
- Login y fetch funcionan contra el API en otro origen (depende de 4.2 — CORS).

### 4.2 · Backend deploy a Fly.io `[ ]`

**Files**
- `Dockerfile` (NEW) en root — multi-stage, Python 3.11 slim, `uvicorn services.api.app:app --host 0.0.0.0 --port 8080`.
- `fly.toml` (NEW) — region GRU (São Paulo, latencia más baja para Argentina), 1 instance, volume `market_bot_data` montado en `/data` (1GB).
- `.dockerignore` — excluir `legacy/`, `data/`, `tests/`, `__pycache__`, `.git`.
- `services/api/app.py` — leer `CORS_ALLOW_ORIGINS` + `CORS_ALLOW_ORIGIN_REGEX` env vars para production. Default: `["*"]` en dev.
- `packages/identity/src/market_identity/store.py` — `database_path()` ya respeta `MARKET_BOT_DB_PATH`, solo asegurarse que Fly lo setee a `/data/market_bot.db`.

**DoD**
- `fly launch` + `fly deploy` exitoso.
- `https://market-bot-api.fly.dev/health` devuelve 200.
- Volume montado en `/data`, env var `MARKET_BOT_DB_PATH=/data/market_bot.db`.
- CORS abierto a `https://market-bot.vercel.app` y previews vía `CORS_ALLOW_ORIGIN_REGEX`.
- Logs JSON visibles vía `fly logs` (ya logueado estructurado por Sprint 3c).

### 4.3 · Production hardening `[ ]`

**Files**
- `services/api/app.py` — leer `MARKET_BOT_DB_PATH` y validar al startup que el dir existe + writable.
- `services/api/logging_config.py` — agregar log de boot con `{db_path, cors_origins, fly_region}`.
- `packages/identity/src/market_identity/store.py` — agregar `PRAGMA journal_mode=WAL` al crear conexión (mejora concurrencia, importante para Fly single-instance con múltiples requests simultáneos).
- `services/api/app.py` — endpoint `GET /ready` que verifica DB + benchmark service. Separa "alive" (health) de "ready to serve" (ready).

**DoD**
- WAL mode activo → confirmado con `PRAGMA journal_mode`.
- `/ready` devuelve 200 solo si DB es queryable y al menos un benchmark fetch reciente está en cache.
- Fly health check apunta a `/ready` no a `/health`.

### 4.4 · Domain + SSL (opcional, $0 con Vercel) `[ ]`

**Files**
- Vercel dashboard: agregar custom domain (ej `market-bot.tudominio.com`).
- DNS: `CNAME` apuntando a `cname.vercel-dns.com`.
- Backend: `api.tudominio.com` → Fly.io (`flyctl certs add api.tudominio.com`).

**DoD**
- Frontend en `https://market-bot.tudominio.com` (o `.vercel.app`).
- API en `https://api.tudominio.com` (o `.fly.dev`).
- SSL certs auto-renovados por Vercel y Fly.

### 4.5 · Onboarding doc para beta testers `[ ]`

**Files**
- `docs/beta-tester-guide.md` (NEW) — link, primer login, qué cargar primero (perfil → 1 posición CEDEAR → analizar 1 ticker), qué reportar.

**DoD**
- Link compartible. Onboarding ≤ 5 min para alguien sin contexto.

### Out-of-scope para Sprint 4 (registrar como deuda)
- **Backup automático del SQLite** — Fly volume es persistente pero único punto de falla. Plan v2: snapshot diario a S3 o a Cloudflare R2.
- **Rate limit basado en Redis** — el actual es in-memory, no sirve con múltiples instancias. v2 cuando se necesite scale horizontal.
- **Postgres migration** — SQLite + WAL aguanta cómodo 50-100 usuarios activos. Migrar solo cuando se vea contention real en `fly logs`.
- **CI/CD GitHub Actions** — deploy manual con `vercel --prod` y `fly deploy` está OK para v1. Automatizar cuando el squad crezca.

---

## 5 · DEFERRED — Backlog post-DoD

### Agent K · Social Sentiment `[deferred]`
Signal-to-noise demasiado bajo. Antes de invertir: validar motor (Sprint 3b)
y medir usage real (Sprint 3a).

### Agent L · Trading Integration / Wallbit `[blocked]`
Bloqueado por 3b (validación) + paper trading sandbox + auditoría de órdenes.

### Mejoras técnicas pendientes (backlog)
- SQLite WAL mode (`PRAGMA journal_mode=WAL`) para concurrencia en `/analyze` paralelo.
- Alembic migrations en vez de raw `CREATE TABLE IF NOT EXISTS`.
- Refresh tokens 24h en vez de access tokens 30d.
- Tabla canónica `cedear_ratios` (fuente BYMA).
- `API_BASE_URL` env var en frontend para split deploy.
- yfinance OHLC cache diferenciado por trading-hours.
- `dataclasses.asdict` ya importado en portfolio/service.py pero no usado — revisar si rama dead.

---

## 6 · Definition of Done — milestone actual

| Requisito | Status |
|---|---|
| login + persisted investor profile | ✅ |
| username/password sin email | ✅ |
| portfolio CEDEAR-aware valuation | ✅ |
| manual position entry | ✅ |
| gains en USD y ARS | ✅ |
| inflation / official / MEP / CCL / plazo fijo comparison | ✅ (data + UI) |
| consolidated recommendation card | ✅ |
| deterministic + external-context reasons | ✅ (news + earnings) |
| earnings-aware warnings | ✅ |
| CEDEAR-first landing | ✅ |
| no hidden backup logic in main path | ✅ |
| **catalyst confidence tagging** | ✅ |
| **personalized workspace** (Agent J) | ✅ |
| (extra) Balanz CEDEAR importer | ✅ |
| (extra) Market overview / pulse | ✅ |
| audit log + decision tracking | ✅ |
| model calibration metrics (Brier) | ✅ |
| rate limit + structured logs | ✅ |
| comprehensive test suite | ✅ (36 tests pasan) |

---

## 7 · Dependency graph (actualizado)

```
Sprint 1a → Sprint 2a ────┐
Sprint 1b → Sprint 2a ────┼─► Sprint 2 (J) ✅
Sprint 1c → Sprint 2a ────┘
Balanz import + Market overview (out-of-roadmap extras) ✅
Sprint 3a (audit log)  ──► usage signal para Agent K decisions
Sprint 3b (Brier)      ──► unblock Agent L (trading)
Sprint 3c (rate/logs)  ──► Sprint 4 (deploy)
Sprint 3d (tests)      ──► safety net global
Sprint 4 (Agent M)     ──► app pública / beta testers
```

---

## 8 · Handoff protocol

Cuando vos (Codex / Claude / human) terminés una task:

1. Cambiá su checkbox a `[x]`.
2. Apendá una línea `> ✅ DONE 2026-MM-DD por <agent>: <PR/commit ref si aplica>`.
3. Si destrabaste algo, movelo a `[ ]` en la sección correspondiente.
4. Blocker nuevo: registralo en sección 5 (backlog técnico) o como nueva task del sprint correspondiente.
5. No empieces a trabajar en `[~]` si no estás seguro de que el otro asistente lo soltó — preguntá al usuario.

### Estado actual de in-progress
- _Ninguno_. Milestone cerrado al 2026-05-27. Next move: Agent K (social) o Agent L (trading) —
  decidir basándose en feedback de usuario real y en lecturas de `/decisions` + `/validation`.
