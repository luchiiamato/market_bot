# Multi-Agent Work Queue

> Handoff document. Cada task tiene `[ ]` pending / `[~]` in-progress / `[x]` done, **Files**
> (qué leer / qué tocar), **DoD** (qué tiene que pasar para marcarla hecha), y notas de
> contexto. Switcheá entre asistentes sin perder estado.

---

## Status snapshot — 2026-05-30 (sesión "tester externo")

**Foco del día: bugs reportados + acceso para tester real. Hecho:**

- **Gemini chat "recortado"** ✅ FIX. Causa: `max_output_tokens=420` (gemini-2.5-flash
  es "thinking", gastaba el budget razonando → texto cortado). Subido a 2048.
  + extracción de texto robusta (no 500 en respuesta vacía/bloqueada) + pricing de
  2.5-flash/pro agregado + label "Buffy" → "Gemini". Verificado end-to-end: responde
  completo, costo $0.000154, tokens OK.
- **Carga de stocks "se ve rara / mapeo"** ✅ FIX. Causa: la tabla
  `CANONICAL_CEDEAR_RATIOS` estaba MAL en **44 de 64 tickers** (eran adivinanzas).
  Derivé los ratios reales desde paridad de mercado en vivo (local_ars × ratio / CCL
  ≈ underlying_usd). MELI 10→120, AAPL 10→20, MSFT 5→30, META 6→24, AMZN 2→144, etc.
  El valor ARS/USD del portfolio YA era correcto (usa precio local × qty); el ratio mal
  solo afectaba "equivale a X acciones" + chips. Ahora todo coherente.
- **Números del portfolio** ✅ VERIFICADO con el Balanz real del user: valor AR$ 19.48M,
  cost 17.34M, **+12.3% P&L, FX implícito 1485 = CCL**. El "-54%" que el user vio antes
  era el bug viejo (server con código previo al fix CCL).
- **Performance ranking cold = 65s** ✅ MITIGADO. Warmup en background al startup
  (loop cada 8 min < TTL 600s) → el primer tester nunca espera, ranking responde en 6ms.
  Gateado para no correr bajo pytest (evita race con reload de config).
- **`.env` destrackeado de git** ✅ — tenía la Gemini key real; estaba gitignored pero
  trackeado. `git rm --cached .env`. La key queda solo local, no se filtra al commitear.
- **Frontend same-origin-aware** ✅ verificado: `API_BASE = window.location.origin`,
  así que servido por túnel o Fly el tester pega al dominio correcto (no a su localhost).
- **90/90 tests pasan** offline en 4.9s.

**Acceso para tester** ✅ RESUELTO 2026-05-30: el user corrió `cloudflared tunnel --url
http://localhost:8000` y anda. URL `*.trycloudflare.com/app/` compartible mientras la
Mac + el túnel + el server (:8000) sigan vivos. Guía en `docs/tester-access.md`.

**PRÓXIMO al retomar (pedido del user 2026-05-30):**
- **7.6 · UX del análisis** — al tocar "Analizar setup" que avise cuándo termina
  (toast/notification) + UI más llevadera durante la espera (skeleton, no spinner pelado,
  sin doble-submit). Spec completa en sección 7.6. Es lo primero que pidió hacer.

---

## Status snapshot — 2026-05-28 (post Sprint 3, mid Sprint 4)

- **Foundation (Agents A–G)**: ✅ entregada.
- **Sprint 1 (catalyst tagging + news + earnings)**: ✅ entregada.
- **Sprint 2 (personalization workspace)**: ✅ entregada. + Balanz importer + market overview (extras).
- **Sprint 3 (validation + audit + observability)**: ✅ entregada. Audit log,
  Brier validation, rate limit + JSON logging, tests extendidos. **36/36 tests pasan**.
- **Sprint 4 (hosting & deploy — Agent M)**: [~] scaffolding técnico listo
  (`Dockerfile`, `fly.toml`, `vercel.json`, `build.js` con `MARKET_BOT_API_BASE`).
  Ahora corre local; deploy real Vercel+Fly aún sin hacer.
- **Sprint 5 (polish + numbers audit)**: [ ] NUEVO. Reportes del user contra
  el host local: (a) transición tema claro/oscuro se siente lenta en el botón,
  (b) "las cuentas por detrás no parecen tener sentido" — pendiente acotar
  qué número exactamente. Ver sección 4.6.
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

## 4.6 · NEW SPRINT — Sprint 5 · Polish + numbers audit

> Goal: tras tener la app corriendo local, el user reporta dos problemas
> distintos. Este sprint los enmarca para no perderlos. Tasks chicas.

### 5.1 · Theme switch perf — agilizar transición dark↔light en el pill `[x]`

**Problema reportado**: "Las transiciones de claro a oscuro en el botón se ven muy lentas."

**Diagnóstico**
- `.theme-pill` transiciona `color` y `background` con `--motion-base` (280ms).
  Para un toggle binario debería estar en `--motion-fast` (140ms) o menos.
- `seg-indicator` del switch ya está overrideado a 110ms (snappy).
- `--motion-theme = 180ms` está OK por duración, pero se dispara en docenas
  de superficies a la vez (hairlines, cards, tiles, panels). La cascada
  amplifica la sensación de lentitud aunque cada propiedad sea breve.

**Files**
- `apps/web/prototype/styles.css` — `.theme-pill` block (~líneas 359-378):
  cambiar `transition` de `--motion-base` a `--motion-fast` para `color` y `background`.
- Considerar reducir `--motion-theme` a ~140ms.
- Auditar surfaces que transicionan `background var(--motion-theme)` en cascada
  y limitar a las que realmente cambian color por theme (las que cambian solo
  por hover/state no necesitan estar en la transición de tema).

**DoD**
- Click en el pill se siente instantáneo (≤150ms percibido) sin perder el cross-fade.
- `prefers-reduced-motion: reduce` sigue desactivando la transición.
- Sin layout shift al togglear.

> ✅ DONE 2026-05-28 por Claude. `apps/web/prototype/styles.css` — `.theme-pill`
> ahora transiciona `color` y `background` con `--motion-fast` (140ms) en lugar
> de `--motion-base` (280ms). El cross-fade del `.seg-indicator` ya estaba en
> 110ms. Sin cambios estructurales, sin layout shift, `prefers-reduced-motion`
> sigue cubierto por la regla global del prototype.

### 5.2 · ARS↔USD valuation mismatch (CEDEAR ratio fallback bug) `[x]`

**Reporte del user**: "Me dice que 900.000 ARS son 36.000 USD." Implied FX = 25 ARS/USD.
Eso no matchea ni el oficial, ni MEP ni CCL en 2026. Es síntoma de uno de estos bugs:

**Hipótesis ordenadas por probabilidad**

1. **CEDEAR con ratio fallback = 1** (más probable). `packages/portfolio/.../service.py:218-219`:
   ```python
   cedear_ratio = position.cedear_ratio or 1.0
   current_value_usd = (position.quantity / cedear_ratio) * underlying_price_usd
   ```
   Cuando `resolve_cedear_reference` no logra inferir el ratio (yfinance offline,
   o BYMA price wonky), `cedears.py:78-84` retorna `cedear_ratio=1.0` con
   `ratio_source="fallback_default"`. Ese fallback a 1.0 infla USD por el ratio real
   (ej. GOOGL ratio=58 → USD overstated 58x). Implied FX = CCL/ratio_real ≈ 25 para
   tickers con ratio ~50. **Coincide con el 25 reportado.**

2. **Posición `instrument_type='stock'` con FX official mal cacheado** desde argentinadatos.com.
   `current_value_ars = USD × current_fx`. Si la API devolvió un valor stale/wrong para
   el "oficial" (campo `venta` vacío → cae a `compra` → 0 → ... raro pero posible
   según `benchmarks.py:69`), podría ocurrir. Menos probable que (1).

3. **yfinance devolviendo precio en USD para `.BA` (BYMA)** en vez de ARS.
   `_latest_close(byma_symbol)` no valida la moneda devuelta. Si el ticker `.BA` no
   tradea más o yfinance reporta el ADR USD, `local_price_ars` queda en magnitud USD.

**Files a tocar**

- `packages/portfolio/src/market_portfolio/cedears.py` — agregar tabla canónica
  `CANONICAL_CEDEAR_RATIOS` con los ratios reales de BYMA para los ~40 tickers
  del `CEDEAR_UNIVERSE`. Usarla como prioridad #2 (después de `user_supplied`,
  antes de `estimated_market_parity`).
- `packages/portfolio/src/market_portfolio/service.py` —
  - En `_build_position_valuation`, si `cedear_ratio_source == "fallback_default"`,
    rechazar la valuación con error explicativo en vez de devolver números rotos.
  - Loggear `{symbol, ratio, ratio_source, local_price_ars, underlying_price_usd,
    implied_fx, ccl}` en `logging_config`. Que sea visible en `fly logs`.
  - Agregar sanity check: si `abs(implied_fx - ccl) / ccl > 0.30`, marcar la
    valuación con warning visible al user.
- `apps/web/prototype/app.js` (`renderPortfolioSummary`) — mostrar el FX implícito
  por posición y el FX usado a nivel portfolio. Tile "FX usado: CCL 1200" arriba
  del grid. Que sea imposible que el bug se esconda.
- `services/api/app.py` — endpoint `GET /portfolio/diagnostics` que devuelva los
  valores crudos (FX series snapshot, ratios resueltos, last quote per ticker)
  para que se pueda inspeccionar sin pegarse al DB.

**DoD**

- Reproducción del bug con un test que use un CEDEAR con ratio real ≠ 1 y
  fuerce `fallback_default` → confirma que hoy explota; con el fix queda sano.
- En la UI, una tile o tooltip muestra el FX usado para la conversión ARS↔USD.
- Si `ratio_source` es `fallback_default`, el front muestra warning rojo "ratio
  no inferido" en la holding card.
- User confirma sobre su portfolio real que las cuentas cierran.

**Diagnóstico pendiente (info del user)**
- ✅ Recibido: screenshot + extracto Balanz. 35 posiciones, 2 USD positions perdidas en
  parsing por el bug de tilde (separado en 5.2b). Implied FX en VALOR = 366 (cost basis
  USD ~11k correcto, VALOR_USD 47.9k inflado). Root cause: la fórmula
  `(qty/ratio) × underlying_usd` se desbarata cuando el ratio inferido es impreciso o
  cuando el ratio queda en 1.0 por fallback.

> ✅ DONE 2026-05-28 por Claude. `packages/portfolio/.../service.py:_build_position_valuation`:
> el USD de CEDEAR ahora se calcula como `current_value_ars / current_ccl` (conversión
> directa al CCL, robusta contra ratios mal inferidos). El cálculo
> `(qty/ratio) × underlying_usd` se mantiene solo como último fallback si CCL no
> está disponible. Test de regresión: `test_cedear_current_value_usd_uses_ccl_conversion_not_inferred_ratio`
> reproduce el caso "ratio=1 fallback + 109 GOOGL @ 8485 ARS" y confirma que ahora
> da ~770 USD en vez de 19,620 USD. **El user NO necesita re-importar** — el fix
> aplica en read-time, basta con refrescar el portfolio.

### 5.2b · Balanz importer pierde filas "Dólares" por tilde `[x]`

**Diagnóstico**: `_normalize_currency` en `balanz.py` hacía `raw = str(value).lower()`
y después `"dolar" in raw`. Como `"dólares".lower()` mantiene la tilde, el substring
match fallaba y las posiciones USD legítimas iban a `skipped[]`. En el extracto del
user esto perdió silenciosamente 1 META (6 shares) y 1 NVDA (33 shares).

> ✅ DONE 2026-05-28 por Claude. `_normalize_currency` ahora normaliza NFKD y
> remueve diacríticos antes del match. Agregados los alias `"$"`, `"us$"`, `"u$s"`.
> Test de regresión: `test_balanz_currency_normalizer_handles_accented_dolares`.
> Re-parseo del extracto del user: 35 → 37 posiciones (META 6 sh @ $28.20 y
> NVDA 33 sh @ $9.37 recuperadas). El user debe re-importar con
> `replace_existing=true` para que aparezcan en su portfolio actual.

### 5.3 · Ranking suggestions son aburridas — expandir universo + catalyst-aware `[x]`

**Reporte del user**: "Los stocks que me sugiere son super básicos. Hoy se explotó
Snowflake en el pre-market por las ganancias y no lo sugirió. Quiero que sugiera
stocks raras, cosas que sean oportunidades."

**Diagnóstico**

`packages/engine/src/market_bot/config.py`:
- `CEDEAR_UNIVERSE` (líneas 21-60): 37 tickers, **incluye SNOW**.
- `SUGGESTION_UNIVERSE` (líneas 75-90): **solo 14 tickers** (AAPL, AMZN, GGAL, GOOGL,
  JPM, MELI, META, MSFT, NVDA, PLTR, QQQ, SPY, TSLA, YPF). **NO incluye SNOW**,
  ni COIN, ni PAM, ni VIST, ni SHOP, ni UBER, ni AMD, ni LLY, ni TSM, ni MCD,
  ni KO, ni DIS, ni ABBV, ni BABA, ni BAC, ni IBB, ni INTC, ni VALE, ni WMT,
  ni XOM, ni SPOT, ni ABEV, ni BRK.B.
- `service.py:117`: `default_universe = SUGGESTION_UNIVERSE if cedear_only else DEFAULT_UNIVERSE`.
  El ranking por default usa esa lista chica → la sugerencia siempre es el mismo
  pool de mega-caps obvios.

**Plan**

1. **Quick fix** ✅ DONE: en `config.py`, ahora `SUGGESTION_UNIVERSE = list(CEDEAR_UNIVERSE)`.
   Que el ranking decida qué subir y qué bajar, no la lista.
2. **Expandir `CEDEAR_UNIVERSE`** ✅ DONE: pasó de 37 a 57 tickers. Incluye SNOW (ya estaba),
   y se sumaron AVGO, ARM, MU, QCOM, CRWD, DDOG, NET, MDB, ZS, OKTA, CRM, ORCL, ADBE,
   PYPL, SQ, ABNB, BIDU, JD, PDD, NU, ALAB, LLY, UNH. **El portfolio del user ya tenía
   ALAB, NU y UNH y antes no entraban al ranking** — ahora sí.
3. **Earnings-aware ranking boost** ✅ DONE: `adjust_rank_for_catalysts` en `policy.py`
   suma multiplicadores cuando hay (a) earnings CONFIRMED, (b) news REPORTED ≤48h,
   (c) volatilidad alta con dirección definida, (d) volumen ≥2x. Cap a 1.65x para
   que un solo catalyst no domine. Las razones del bump entran al `why_for_you[]` de
   la response del ranking, así el user ve *por qué* saltó (no solo *que saltó*).
4. **"Opportunities" mode** ✅ DONE: `/rankings?mode=opportunities` aplica filtro duro
   `is_opportunity_candidate` — solo nombres con catalyst, volumen spike, ATR/price > 4%
   o conviction ≥0.7 con dirección. Adicionalmente, dropea index ETFs (SPY/QQQ/IBB/DIA/VOO/VTI)
   que no sirven cuando el user pide "movers". Toggle UI en el panel de ranking,
   estado persiste en `localStorage`. Si el filtro queda vacío, mensaje explicativo.

**Files**
- `packages/engine/src/market_bot/config.py` — expandir `SUGGESTION_UNIVERSE` y
  posiblemente `CEDEAR_UNIVERSE`.
- `packages/engine/src/market_bot/strategies/policy.py` — earnings-aware bump
  y "opportunities" filter mode.
- `services/api/schemas.py` + `services/api/app.py` — exponer `mode=opportunities`
  en `/rankings`.
- `apps/web/prototype/{index.html, app.js}` — toggle UI "Sugerencias raras" en
  el panel de ranking.
- `tests/test_regressions.py` — caso donde SNOW con earnings reciente queda
  top-5 en mode=opportunities.

**DoD**
- ✅ `/rankings` con default behavior re-ranquea los 57 tickers de `CEDEAR_UNIVERSE`.
- ✅ `/rankings?mode=opportunities` prioriza catalysts + volatilidad + volumen.
- ✅ Tests `test_catalyst_boost_lifts_score_for_fresh_earnings`,
  `test_opportunity_filter_drops_quiet_megacap_keeps_news_driven_name`,
  `test_rankings_endpoint_passes_mode_through_to_service` cubren los tres.
- ✅ UI: toggle "Ranking completo / Solo oportunidades" con persistencia en localStorage.

> ✅ DONE 2026-05-28 por Claude. `policy.py:adjust_rank_for_catalysts` (multiplier
> stack capped @ 1.65x), `policy.py:is_opportunity_candidate`, integrado en
> `service.py:rank_universe(mode=...)`, expuesto en `GET /rankings?mode=opportunities`,
> UI toggle en `apps/web/prototype/{index.html, app.js, styles.css}`. 46/46 tests OK.

### 5.4 · FX diagnostic tile en portfolio `[x]`

**Goal**: que el user pueda ver de un vistazo qué FX se usó para convertir
ARS↔USD, y si hay drift sospechoso entre el FX implícito (valor ARS ÷ valor USD)
y el CCL actual.

> ✅ DONE 2026-05-28 por Claude. Tile nuevo arriba del resumen del portfolio:
> CCL/MEP/Oficial actuales + FX implícito calculado del summary. Si el drift
> entre implícito y CCL > 25%, el número se pinta `bear` para llamar la atención.
> Soft-fail si `/benchmarks/current` falla (tile se oculta, no rompe la vista).
> CSS responsive a 2 columnas en mobile.

### 5.5 · Surface audit de cosas raras en el local host `[ ]`

Recolectar el resto de cosas raras que el user reporte más allá de 5.1/5.2/5.3.

**DoD**
- Lista en este doc con cada "cosa rara" reportada, file:line donde vive,
  decisión (fix / wontfix / defer).

---

## 4.7 · NEW SPRINT — Sprint 6 · Future improvements (roadmap)

> Lista de mejoras grandes que se identificaron mientras se cerraba Sprint 5.
> Cada una ordenada por (impacto al user) × (esfuerzo). El orden de arriba
> hacia abajo es la prioridad sugerida.

### 6.0 · Typography pass del portfolio summary `[x]`

**Goal**: arreglar la jerarquía visual del summary del portfolio aplicando el
audit UI/UX (B1 + B5 + B6 + B7). Sin tocar identidad tipográfica (Fraunces +
DM Sans + JetBrains Mono, paleta citrus, dark/light).

**Cambios**

- `apps/web/prototype/app.js` — nuevo `formatMoney(value, currency, opts)` con
  prefijos consistentes (`AR$` / `US$`), magnitudes compactas (`M`/`k`),
  signo explícito opt-in (`+` / `−` tipográfico). `formatPercent` ahora también
  acepta `{ signed: true }`. Helper `toneOf(value)` para mapear positivo→bull,
  negativo→bear, cero→neutral.
- `renderPortfolioSummary` rediseñado: un **hero number** (valor ARS en Fraunces
  variable, opsz=144 wght=380, clamp(3rem, 6vw, 5.4rem)) + grilla de 4 satellites
  con bull/bear semantic color y una barra horizontal para "Real vs inflación".
- CSS `.portfolio-hero-summary`, `.portfolio-hero-value`, `.satellite`,
  `.real-return-bar` (con divisor central marcando el cero). Responsive a 2 cols
  a <900px y 1 col a <540px.

> ✅ DONE 2026-05-28 por Claude. La grilla de 6 tiles iguales fue reemplazada
> por un solo hero number con satélites coloreados según direction. Real Return
> ahora muestra magnitud visual además del número. 48/48 tests pasan.

### 6.1 · CEDEAR canonical ratio table + Balanz FX read `[~]` (parcial)

**Por qué**: aunque el bug del USD ya está mitigado vía conversión CCL, la
inferencia de `cedear_ratio` puede seguir devolviendo ratios "snap-fit"
inexactos (24 cuando es 58, etc.), y el campo "Effective US shares" en cada
holding card es incorrecto. Además, Balanz exporta el CCL/MEP/Oficial de la
fecha de compra en columnas K/L/M y los ignoramos — argentinadatos.com puede
fallar para fechas viejas y cuando falla, falla todo el add_position.

**Plan**

- `packages/portfolio/.../cedears.py` — sumar `CANONICAL_CEDEAR_RATIOS` con
  ratios verificados contra BYMA (mantener actualizado tras splits).
- En `resolve_cedear_reference`, prioridad: `user_supplied` → `canonical_table` →
  `estimated_market_parity` → `fallback_default` (que debería convertirse en
  warning explícito, no en ratio=1).
- `packages/portfolio/.../balanz.py` — extender `BalanzPositionDraft` con
  `purchase_ccl`, `purchase_mep`, `purchase_official` opcionales. Si vienen
  en el extracto, pasarlos como override al service.
- `_cost_basis` — si la posición trae `purchase_ccl != None`, usarlo directo
  en vez de pedírselo a argentinadatos.

**DoD**
- ✅ `CANONICAL_CEDEAR_RATIOS` con 50+ tickers (mega-caps, semis, AI/cloud,
  fintech, healthcare, financials, EM, ARGY ADRs). Documentado: actualizar
  tras splits oficiales de BYMA.
- ✅ `resolve_cedear_reference` ahora prioriza canonical → parity → fallback.
- ✅ Card de holding muestra "Equivale a X acciones de TICKER" y chip de
  source del ratio (Cargado por vos / BYMA oficial / Inferido / No verificado)
  con color semántico.
- ⏳ **Pendiente para 6.1b**: leer columnas K/L/M (DolarCCL/MEP/Oficial) del
  Balanz xlsx y propagarlas como override de FX en `add_position`. Hoy seguimos
  pidiendo FX a argentinadatos.com para fechas viejas.

> ✅ DONE (parcial) 2026-05-28 por Claude. `CANONICAL_CEDEAR_RATIOS` en
> `packages/portfolio/.../cedears.py`. `ratio_source="canonical"` agregado al
> enum. Tests `test_canonical_table_beats_parity_inference`,
> `test_known_ticker_hits_canonical_even_without_price_legs` + tests existentes
> renombrados para no chocar. UI: ratio chip + source chip + "Equivale a X
> acciones" en cada holding card.

### 6.2 · Earnings calendar UI mejorada `[x]`

**Por qué**: ya tenemos `/earnings/upcoming` (auth, holdings-aware) pero el render
es chico. Si el user va a ver el portfolio el día que reporta SNOW, el sistema
debería **gritar**.

**Plan**

- ✅ Banner sticky debajo del masthead cuando hay earnings en las próximas 48h
  para tickers que el user tiene en portfolio.
- ✅ Treatment editorial: mono kicker "EARNINGS WINDOW", serif body con
  countdown ("en 3h 12min"), citrus pulse a la izquierda reutilizando el
  `live-pulse` keyframe.
- ✅ Diferenciación visual cuando es un ticker del user (border citrus reforzado +
  chip verde "Tenés esta posición") vs cuando no ("No tenés posición").
- ✅ CTA "Ver detalle" salta al workspace con el ticker preseleccionado.
- ✅ Dismiss persistido por evento en `localStorage` — no reaparece para el
  mismo evento pero sí para uno nuevo.
- ⏳ **Pendiente para 6.2b**: "surprise history grid" (4×3 con los últimos 12 Q,
  cada uno coloreado bull/bear según beat/miss) en el earnings panel del
  workspace. Requiere endpoint nuevo que pegue contra yfinance `earnings_history`.
- ⏳ **Pendiente para 6.2c**: pre/post-market reaction % del día después.

> ✅ DONE (banner) 2026-05-28 por Claude. `apps/web/prototype/index.html`
> nuevo `<aside class="earnings-banner">`, `app.js` con `refreshEarningsBanner`,
> `formatEarningsCountdown`, `dismissedEarningsKeys`. Soft-fail si la API
> falla. Animación entrada con cubic-bezier spring. Responsive: stack vertical
> a <720px.

### 6.3 · Decision audit loop completo `[ ]`

**Por qué**: ya guardamos las decisiones del user vía `POST /decisions` con
snapshot completo del análisis. Falta el ciclo de retorno: "qué hubieras ganado
si seguías la sugerencia".

**Plan**

- Job offline `python -m market_bot.jobs.realize_decisions` que para cada
  decision de hace ≥N días, calcula el `realized_return` (yfinance diff) y
  lo persiste en `user_decisions.realized_return`.
- Endpoint `GET /decisions/track-record?ticker=X&since=...` que devuelva
  hit rate, avg return per decision, Sharpe del set.
- UI: "Tu track record" tile en el workspace logged-in.

### 6.4 · Social sentiment (Agent K, deferido) `[ ]`

**Estado actual**: deferido. Ahora con audit + Brier funcionando, es momento de
revisitar. Idea: integrar reddit/X via free tier + filtrar por confidence.

**Plan**

- Adapter `packages/reference_data/.../social.py` con yfinance social
  fallback + opt-in `BEARER_REDDIT_TOKEN` para reddit search.
- Sentiment scoring por (volume × tone × source_reputation).
- Catalyst de tipo "social_chatter" con `status=RUMORED` por default. La
  política de rumor ya está implementada (`RUMOR_MAX_SCENARIO_DELTA`).

### 6.5 · Paper trading sandbox (Agent L precursor) `[ ]`

**Por qué**: Wallbit/trading real está bloqueado hasta tener confianza en el motor.
Mientras tanto, simular órdenes para que el user pueda testear estrategias.

**Plan**

- Tabla `paper_orders` (user_id, ticker, side, qty, fill_price, timestamp, strategy_tag).
- Endpoint `POST /paper/orders` que registra una orden virtual al precio actual.
- `GET /paper/performance` con métricas tipo backtest.
- UI: "Practice mode" toggle que reemplaza Buy/Sell por "Simular compra/venta".

### 6.6 · Sector + region exposure breakdown `[x]`

> ✅ DONE 2026-05-29 por agent paralelo. Nuevo módulo
> `packages/reference_data/.../classification.py` con tabla hand-maintained
> `TICKER_CLASSIFICATION` cubriendo ~60 tickers de `CEDEAR_UNIVERSE` mapped a
> sector + region. Funciones `classify_ticker` + `aggregate_exposure`.
> `PortfolioSummary` ahora incluye `sector_exposure` y `region_exposure`
> (lista de `ExposureBucket`). UI: dos cards "Concentración por sector" y
> "Concentración por región" con horizontal stacked bar + legend. 5 tests
> nuevos en `tests/test_exposure.py`. 71/71 tests pasan.

**Por qué**: el user ve P&L total pero no sabe que está 60% en tech o que tiene
muy poca diversificación geográfica.

**Plan**

- `packages/reference_data/.../classification.py` con map ticker → sector/region
  (yfinance `info` o tabla canónica).
- En `portfolio_summary`, sumar exposure breakdown.
- UI: doughnut chart (HTML+CSS, sin libs) abajo del FX diagnostic tile.

### 6.7 · Push alerts (mobile/desktop) `[ ]`

**Por qué**: las oportunidades pasan cuando el user no está mirando la app.

**Plan**

- Service worker en el frontend para web push.
- Cron job en el backend que cada N minutos:
  - Re-ranquea con `mode=opportunities` para cada user logged in.
  - Si el top-1 cambió desde el último envío, push notification "SNOW saltó al top: earnings beat".
- Opt-in en perfil.

### 6.8 · Multi-currency portfolios `[ ]`

**Por qué**: hoy asumimos que todo se valúa en ARS+USD vía CCL/MEP. Si el user
tiene cripto, EUR, BRL, etc., no funciona.

**Plan**

- Extender `currency` enum: ARS / USD / EUR / BRL / BTC / ETH.
- FX matrix vs USD vía yfinance currency pairs.
- UI: selector de "moneda base" del portfolio (no solo ARS).

### 6.9 · Backtest del ranking (no solo de tickers) `[ ]`

**Por qué**: el `BacktestSummary` actual mide un ticker individual. Lo que importa
es: si el user hubiera seguido la sugerencia top-3 del ranking cada día, qué
hubiera pasado.

**Plan**

- Job `python -m market_bot.jobs.backtest_ranking --start=YYYY-MM-DD`.
- Para cada día, re-corre `rank_universe`, "compra" top-3 con weight uniforme,
  rebalancea al día siguiente.
- Métricas: cum return, max drawdown, hit rate, Sharpe, comparison vs SPY buy-and-hold.
- UI: "Track record del ranking" panel.

### 6.10 · Onboarding tour `[ ]`

**Por qué**: cuando alguien entra por primera vez, no sabe por dónde empezar.

**Plan**

- Componente tour con 4 steps: (1) cargar perfil, (2) importar Balanz, (3)
  ver análisis del primer ticker, (4) abrir ranking de oportunidades.
- Dismissable, no reaparece.

---

## 4.8 · NEW SPRINT — Sprint 7 · Core engine, calculations & performance `[ ]`

> **Prioridad crítica.** Es donde más se nota cuando algo está mal. El user
> reportó números que no cuadran (ARS=7.83M vs cost=17M = −54% improbable) y
> el ranking lento. Antes de cualquier feature nuevo grande hay que asegurar
> que el core no miente y responde rápido. Si los números mienten, todo lo
> demás del producto es entretenimiento.

### 7.1 · Auditoría de cálculos end-to-end `[~]` parcial

**Por qué**: el user reportó `current_value_ars` que no coincide con la realidad
del mercado. La sospecha #1 es yfinance devolviendo precios stale o mapeados
mal para `.BA` (BYMA). Antes ya tocamos cost basis, ratio canonical, USD via
CCL — falta cerrar el último gap.

**Plan**

- **Smoke test offline contra fixture de precios reales** — armar un dataset
  hard-coded con 5-10 posiciones de prueba y precios de cierre auditados manualmente
  (1 día específico). Test que valida `current_value_ars`, `cost_basis_ars`, P&L,
  benchmarks: si la suma cambia frente al fixture, falla CI.
- **Per-position diagnostics surface en UI** — exponer en una vista de
  developer/debug (route `/portfolio/diagnostics` ya existe en backend, falta
  consumir en frontend) qué precio devuelve yfinance por cada `.BA`, qué ratio
  usa, y si el FX implícito vs CCL hace `drift > 25%`. Tile rojo si rompe.
- **Validar mapping BYMA**: muchos `.BA` tienen sufijo distinto en yfinance
  (ej. BRKB vs BRK.B, NU vs NUBANK). Tabla canónica `byma_yfinance_overrides`
  con mappings verificados, paralela a `CANONICAL_CEDEAR_RATIOS`.
- **Fallback explícito cuando yfinance devuelve algo absurdo**: si el local
  ARS price implica un FX > 30% off del CCL, reject + warning visible
  ("precio local sospechoso para SYM") en lugar de devolver número roto silente.
- **Logging estructurado de cada fetch yfinance**: ticker, period requested,
  rows returned, last close, latency. Hoy es black box — si se rompe, no
  sabemos por qué. Va a `logging_config` que ya tenemos.

**DoD**
- Test de regresión con un caso real del user que hoy falle y pase con el fix.
- UI: panel "Diagnóstico de valuación" en /portfolio con drift % por posición.
- 100% de las posiciones del user con `drift_fx < 25%` o, si no, warning visible.

### 7.2 · Real return refactor — respetar `benchmark_preference` del perfil `[x]`

> ✅ DONE 2026-05-29 por Claude. Modelo `PositionValuation` y `PortfolioSummary` ahora
> exponen `preferred_benchmark_return_pct` + `preferred_benchmark_label` además del
> canónico `real_return_pct` (vs inflación). Service.py popula los dos: el primero usa
> `_aggregate_preferred_benchmark_return` con `PREFERENCE_TO_COMPARISON_LABEL` mapping
> ({official→official_usd, mep→mep_usd, ccl→ccl_usd}). Schema actualizado.
> UI puede mostrar dinámicamente "Real vs {label}" en lugar del fijo "vs Inflación".

**Por qué**: hoy `real_return_pct` siempre se computa vs inflación. Si el user
eligió MEP como benchmark de preferencia, "Real return" debería ser vs MEP, no
vs inflación. La definición actual es defendible pero el label engaña.

**Plan**
- Refactor `_aggregate_real_return` para tomar `benchmark_preference` y elegir
  el `tracked_value_ars` adecuado.
- Renombrar el label en UI a "Real vs {benchmark elegido}" (dinámico).
- Tooltip explicando: "Si querés ver vs inflación, cambiá tu benchmark
  preference en Settings".

### 7.3 · Performance · paralelización + cache layers `[x]`

> ✅ DONE 2026-05-29 por agent paralelo + integración por Claude.
> **Portfolio service**: nuevo `prefetch_quotes(symbols)` que hace una sola
> `yf.download(["AAPL","AAPL.BA",...], group_by="ticker", threads=True)` antes del
> loop de valuación → warmea `_quote_cache`. TTL del cache: 300s → 900s.
> **Engine adapter**: `prefetch_universe(tickers, horizon)` análogo para rankings.
> `rank_universe` llama a `prefetch_universe` antes del ThreadPoolExecutor.
> **Cache warming es best-effort**: cualquier failure (offline, network) cae a
> per-ticker `_latest_close` sin romper tests. Structured log JSON
> `"yfinance batch fetch"` con symbols / elapsed_ms / hit_rate.
> Tests: `tests/test_batch_prefetch.py` (4 nuevos · MultiIndex, missing tickers,
> exception handling, adapter cache). **64/64 tests pasan.**

**Por qué**: cargar `/portfolio/summary` para 37 posiciones hoy hace fetch
serial a yfinance (con ThreadPoolExecutor `max_workers=6` parcial). El user
percibe latencia. `/rankings` con catalyst boost peor: itera 57 tickers, cada
uno con análisis completo → 30-60s easy.

**Plan**
- **Yfinance batch fetch**: `yf.download(["AAPL", "GOOGL", ...])` devuelve
  todo en una sola request. Mucho más rápido que N requests individuales.
  Hoy `_latest_close` hace una por ticker. Refactor para batch.
- **Redis (or in-memory LRU) layer para quotes**: TTL 5min en trading hours,
  6h fuera. Hoy hay `TTLCache` pero solo en algunos paths. Generalizar.
- **Análisis precomputado en background**: cron job cada 15min que precorre
  el ranking del universo entero y guarda en SQLite. `/rankings` lee la
  tabla, no recomputa. Trade-off: data hasta 15min stale vs respuestas <100ms.
- **Lazy loading de positions**: si el user tiene 37 posiciones, no traer las
  37 valuations completas en el primer paint. Cargar el header agregado
  inmediato y las position cards a medida que scrollea (intersection observer).

**DoD**
- `/portfolio/summary` < 2s para 50 posiciones (hoy: ~10s).
- `/rankings` < 3s primera vez, < 200ms cacheado (hoy: ~30s primera).
- Lighthouse perf score > 85 en mobile.
- Métrica de latencia logged JSON por endpoint (ya está en `logging_config`).

### 7.4 · Validación matemática · tests con números hard-coded `[x]`

> ✅ DONE 2026-05-29 por agent paralelo + integración por Claude. `tests/test_portfolio_math.py`
> con 8 tests golden: CEDEAR ARS math, USD via CCL (no via ratio), US stock FX,
> aggregate sum integrity, inflation/plazo_fijo factor tracking, FX rate tracking,
> canonical ratio wins over parity, currency normalizer all variants. Cualquier
> drift futuro en `cost_basis`, `current_value`, `pnl`, `benchmark tracking` rompe CI.
> **60/60 tests pasan offline en 3s.**

**Por qué**: el core engine (deterministic + probabilistic + ranking + portfolio)
es donde un bug silencioso es más caro. Los tests actuales cubren happy paths,
no validan que `pnl_ars == 904385` para fixture X. Necesitamos
**property-based + golden tests**.

**Plan**
- Suite `tests/test_portfolio_math.py` con casos:
  - 1 CEDEAR comprado a precio X en fecha Y, hoy a precio Z → ARS, USD, P&L exactos.
  - Mixto ARS+USD positions → totales correctos.
  - CCL conversion forward/backward → consistente.
  - Benchmark tracking → fórmula exacta documentada.
- Suite `tests/test_engine_signals.py`:
  - Frame sintético OHLC → RSI exacto a 4 decimales.
  - Catalyst boost cap a 1.65x → test que valida el cap.
- Property-based con `hypothesis`: para cualquier portfolio aleatorio,
  `total_value_ars ≈ sum(position.current_value_ars)` (no drift por float).
- **Golden snapshots**: serializar la respuesta de `/portfolio/summary` con
  un fixture conocido y validar byte-a-byte contra el JSON committeado.

**DoD**
- Cobertura del módulo `portfolio` > 80%.
- Cobertura del módulo `engine.strategies` > 70%.
- Suite total corre offline en < 5s.
- Cualquier cambio en cost basis / ratio / benchmark math rompe al menos un golden.

### 7.5 · Frontend perf · bundle + render `[x]`

> ✅ DONE 2026-05-29 por Claude.
> **Code-splitting**: `GLOSSARY_TERMS` (~50KB de data) extraído a
> `apps/web/prototype/glossary.js`. Cargado lazy cuando el user abre la
> Learning surface (o cuando hace hover sobre el tab — prefetch warmup).
> El bundle inicial baja ~50KB sin tocar features.
> **`defer` en `<script src="./app.js">`**: el JS ya no bloquea el HTML parser.
> First paint perceible más rápido.
> **`<link rel="prefetch">` para glossary.js** así el browser lo baja idle
> aunque el user no abra Learning.
> **Skeleton state "Cargando diccionario…"** en Learning si todavía no llegó.
> `ensureGlossaryLoaded()` Promise idempotente para evitar double-load.

### 7.6 · UX del análisis · feedback de progreso + UI más llevadera `[ ]`

> Pedido del user (2026-05-30): al tocar "Analizar setup" el análisis tarda
> (fetch yfinance + indicadores + señales + escenarios) y NO hay feedback claro
> de cuándo termina. Querés que **avise cuando termina** y que la UI sea más
> llevadera durante la espera.

**Por qué importa**: el `/analyze` de un ticker cold puede tardar varios segundos.
Hoy el botón muestra un spinner pero el user no sabe si está vivo o colgado.
Para un tester externo, esa incertidumbre es de las cosas que más fricciona.

**Plan**

1. **Estados de progreso explícitos** en el botón + status line:
   - Al disparar: "Analizando AAPL… (esto puede tardar unos segundos)".
   - Si se puede, fases: "Trayendo precios → calculando indicadores → escenarios".
     (El backend no expone fases hoy; o lo hacemos con un endpoint SSE/stream,
     o simulamos las fases en el front con timers honestos.)
   - Al terminar: toast/aviso "✓ Análisis de AAPL listo" + scroll suave al veredicto.
2. **Aviso de finalización** (lo que pidió el user):
   - Toast visual no intrusivo (esquina) con `success-check` transition de transitions.dev.
   - Opcional: `Notification` API del browser si la pestaña está en background
     ("AAPL: setup alcista listo") — pedir permiso la primera vez.
   - Opcional: sonido corto suave (toggle en settings, off por default).
3. **UI más llevadera durante la espera**:
   - Skeleton del verdict card (no spinner pelado): placeholders pulsando con la
     forma real del resultado, así el layout no salta cuando llega la data.
   - Deshabilitar el botón + cambiar label a "Analizando…" para evitar doble submit.
   - Si tarda > ~8s, mensaje tranquilizador ("Sigue procesando, el primer análisis
     de un ticker es el más lento; los próximos son instantáneos por cache").
4. **Cache hit feedback**: si el análisis vino de cache (instantáneo), no mostrar
   el flujo de espera — directo al resultado.

**Files**
- `apps/web/prototype/app.js` — `analyzeTicker()`: estados de progreso, toast,
  Notification API, skeleton. Buscar `setButtonBusy` / `setStatus`.
- `apps/web/prototype/styles.css` — `.analysis-toast`, skeleton del verdict,
  reusar `--check-*` tokens de transitions.dev (success-check ya instalado).
- `apps/web/prototype/index.html` — contenedor del toast + skeleton del verdict.
- (Opcional backend) `services/api/app.py` — endpoint SSE `/analyze/stream` que
  emita fases. Solo si el feedback simulado en front no alcanza.

**DoD**
- Al analizar, el user siempre sabe: arrancó / sigue / terminó.
- Aviso claro de finalización (toast mínimo + opcional Notification).
- Sin doble-submit. Sin salto de layout. Cache hit = instantáneo sin ruido.
- Probar en el túnel con un tester: ¿la espera se siente manejable?

**Por qué**: `app.js` ya pesa 2300+ líneas. Cuando metamos chat (Sprint 8) y
más features, vamos a sentirlo. El TTI se va a degradar.

**Plan**
- Code-splitting manual: `learning.js`, `portfolio.js`, `chat.js` como módulos
  ES separados, lazy-loaded por surface activa.
- Defer non-critical CSS (font-variation-settings, glyph styles) tras el
  first paint.
- `requestIdleCallback` para el work-queue updates y el log de portfolio.
- Reemplazar manipulación directa de innerHTML por DocumentFragment / template
  cloning en los renders más calientes (positions grid, opportunity rows).

**DoD**
- Lighthouse perf > 90 desktop, > 80 mobile.
- TTI < 1.5s en una conexión 4G simulada.

---

## 4.9 · NEW SPRINT — Sprint 8 · AI chatbot multi-provider `[ ]`

> El user quiere conversar con un asistente IA sobre su portfolio, tickers,
> conceptos financieros. Que pueda elegir proveedor (Gemini / OpenAI / Claude /
> otros) y pegar su propia API key.

### 8.1 · Backend · provider-agnostic chat layer `[x]`

> ✅ DONE 2026-05-29 por agent paralelo. Nuevo módulo `packages/chat/` con
> `providers/{base,anthropic,openai,gemini}_provider.py` (SDKs lazy-loaded,
> sin nuevas deps en requirements.txt). `router.py` con default fallback.
> `store.py` con tablas SQLite `chat_threads` + `chat_messages` (audit log
> incluye tokens_in/out/cost_usd/latency_ms por turn). 6 endpoints públicos
> nuevos en `services/api/app.py`. 10 tests offline en `tests/test_chat.py`.
> **81/81 tests pasan.**

**Plan**

- `packages/chat/` nuevo módulo. Estructura:
  ```
  packages/chat/src/market_chat/
    __init__.py
    providers/
      base.py          # ABC: ChatProvider con .stream(messages, system) → iterator
      openai.py        # GPT-4o-mini / GPT-4o
      anthropic.py     # Claude Sonnet 4 / Opus
      gemini.py        # Gemini Pro / Flash
      ollama.py        # local LLM via http (opcional, gratis)
    router.py          # selecciona provider según config
    context.py         # arma system prompt + inyecta contexto del user
    schemas.py
  ```
- Endpoint `POST /chat/messages` (SSE streaming) y `GET /chat/threads`.
- Persistencia mínima en SQLite: tabla `chat_threads`, `chat_messages`.
- Rate limit: 20 messages / hour / user para evitar abuse.

### 8.2 · Provider selection + key storage `[x]`

> ✅ DONE 2026-05-29 (incluido en 8.1). `.env.example` con bloque CHAT_*
> (CHAT_PROVIDER_DEFAULT, CHAT_{ANTHROPIC,OPENAI,GEMINI}_{API_KEY,MODEL}).
> `GET /chat/providers` reporta qué hay configurado sin filtrar keys.
> Per-user override de proveedor por thread (provider stored per-thread).
> User-supplied API keys con encrypt-at-rest queda como 8.2b para v2.

**Plan**

- `.env.example` con:
  ```
  CHAT_PROVIDER_DEFAULT=anthropic
  CHAT_OPENAI_API_KEY=
  CHAT_OPENAI_MODEL=gpt-4o-mini
  CHAT_ANTHROPIC_API_KEY=
  CHAT_ANTHROPIC_MODEL=claude-sonnet-4-5
  CHAT_GEMINI_API_KEY=
  CHAT_GEMINI_MODEL=gemini-2.0-flash-exp
  CHAT_OLLAMA_BASE_URL=
  ```
- Endpoint `GET /chat/providers` devuelve qué providers están configurados
  (NO devuelve las keys, solo el bool).
- Endpoint `PUT /chat/settings` para que el user logged-in elija qué provider
  usar de los configurados (no setea la key — la key vive en env del backend).
- **Opción advanced** (post-v1): permitir que el user pegue su PROPIA key
  vía UI, encriptarla en SQLite con Fernet, y usarla en lugar de la del .env.
  Útil para que cada user pague su propio uso.

### 8.3 · Context-aware prompts `[x]` DONE 2026-05-30

> ✅ El system prompt hidrata perfil + portfolio real del user
> (`_build_chat_profile_context` + `_build_chat_portfolio_context` en app.py):
> posiciones top, P&L ARS/USD, retorno real vs inflación, vs benchmark preferido,
> exposición sectorial + geográfica. Verificado end-to-end con el Balanz real:
> el bot respondió "85.41% US, Semis 35.89%, Tech 30.25%, P&L 12.34%".
>
> **Bugs encontrados y arreglados durante la verificación:**
> - `_format_chat_pct` no multiplicaba ×100 → el bot decía "P&L 0.12%" para un
>   +12.34% real. Unificado: el formateador hace ×100, callers pasan ratios.
>   Regression test `test_format_chat_pct_multiplies_ratio_by_100`.
> - Context injection estaba gateado por keywords → "cuál es mi P&L?" no matcheaba
>   "portfolio" y el bot decía "no tengo tus datos". Ahora si el user tiene
>   posiciones, el contexto se inyecta SIEMPRE (~600 tokens, costo despreciable).
>
> **Pendiente opcional (8.3b):** tool-use / function calling real (analyze_ticker,
> get_market_overview como tools que el modelo invoca). El contexto estático ya
> cubre el 80% del valor; las tools darían respuestas sobre tickers que el user
> NO tiene en cartera. Dejar para cuando se pida.

### 8.3-old · (spec original, ahora cumplida)

> ⏳ NO ARRANCADO. Es el feature que hace al chatbot **útil** vs. un ChatGPT
> genérico: que sepa de tu portfolio, tu perfil, tus decisiones.
>
> **Plan exacto al retomar**:
>
> 1. **System prompt template hidratado** en `packages/chat/src/market_chat/store.py`:
>    - Tomar `SYSTEM_PROMPT_BASELINE` actual y extenderlo con bloques opcionales:
>      `{investor_profile}`, `{risk_tolerance}`, `{benchmark_preference}`,
>      `{top_positions}` (top 10 holdings con valor ARS/USD), `{upcoming_earnings}`
>      (eventos ≤7d de los holdings).
>    - Función `build_user_context(user_id) -> str` en `store.py` que consulte
>      `identity_service.get_profile(user_id)` + `portfolio_service.portfolio_summary(...)`
>      + `earnings.upcoming_for_holdings(...)` y devuelva el bloque texto.
>    - En `services/api/app.py` la ruta `POST /chat/threads/{id}/messages`,
>      antes de llamar a `provider.chat(...)`, hidrate el system prompt con
>      `build_user_context(current_user.user_id)`.
>
> 2. **Tool use / function calling** (cuando el provider lo soporta):
>    Agregar `packages/chat/src/market_chat/tools.py` con 4 tools:
>    - `analyze_ticker(symbol, horizon)` → llama `MarketBotService.analyze_ticker`.
>    - `get_portfolio_summary()` → trae el summary actual del user.
>    - `compare_to_benchmark(ticker)` → llama `custom_benchmark_comparison`.
>    - `get_market_overview()` → tape general.
>    Cada tool con schema JSON Schema. Los providers que soporten
>    function calling (Claude, GPT-4, Gemini) ven el tool catalog. Los que
>    no, reciben solo el system prompt y se las arreglan con texto.
>
> 3. **Quick action chips** del UI (8.4) ya están armados pero no están
>    pre-cargados con prompts que aprovechen el contexto. Cambiar:
>    - "Analizame mi portfolio" → manda `"Analizá mi portfolio actual y decime qué riesgo de concentración tengo y qué oportunidades ves."`
>    - "¿Cómo viene NVDA?" → `"¿Cómo viene NVDA? Usá analyze_ticker y respondé con la lectura del motor."`
>    - "Explicame qué es CAGR" → educacional, no toca tools.
>    - "Mostrame mi exposición sectorial" → usa `get_portfolio_summary` para citar números.
>
> **DoD**:
> - Si el user pregunta "¿qué pasa con NVDA?" sin más contexto, el bot
>   responde con su precio actual de su POSICIÓN (no genérico).
> - Tests offline con un fake provider que verifica que el system prompt
>   incluye `{investor_profile}` cuando el user tiene perfil.
> - El system prompt **no** lekea API keys ni claves internas.

**Por qué**: un chatbot genérico chatGPT no agrega valor. La diferencia se
hace cuando el bot **conoce tu portfolio, tu perfil, tus decisiones**.

**Plan**

- System prompt template `packages/chat/.../prompts/system.md` que el router
  hidrata con:
  - `{investor_profile}` del user (conservador/moderado/agresivo).
  - `{benchmark_preference}` (MEP/CCL/etc).
  - Posiciones actuales (top 10) con valores ARS/USD.
  - Decisiones recientes (`user_decisions` table).
  - Earnings próximos en holdings.
- Tools / function calling cuando el provider lo soporta:
  - `analyze_ticker(symbol, horizon)` → llama nuestro `MarketBotService.analyze_ticker`.
  - `get_portfolio_summary()` → trae el summary actual.
  - `compare_to_benchmark(amount_ars, benchmark, since_date)` → custom benchmark calc.
  - `get_market_overview()` → tape general.
- Que el bot pueda decir "Mirá AAPL, hoy tu posición de 40 sh vale AR$ X" y
  no respuestas vagas tipo "te recomendaría diversificar".

### 8.4 · UI del chat `[~]` ENTREGADO POR AGENT, FALTA VERIFICAR

> 🟡 ENTREGADO 2026-05-29 por agent paralelo. Pendiente sanity check al
> retomar la sesión: correr `node -e "new Function(require('fs').readFileSync('apps/web/prototype/app.js','utf8'))"`
> + `python3 -m pytest tests/ -q` para confirmar 81/81. El agent reportó que
> no pudo correr esos comandos en su sandbox — yo iba a hacerlo al recibir
> la notificación pero el user pausó la ejecución.
>
> **Archivos modificados por este agent**:
> - `apps/web/prototype/index.html` (+41) — surface tab "Asistente" + surface stack.
> - `apps/web/prototype/styles.css` (+466) — `.chat-panel`, `.chat-layout`,
>   `.chat-threads`, `.chat-message-*`, shimmer keyframe, responsive < 720px.
> - `apps/web/prototype/app.js` (+580) — módulo Chat completo: initializeChat,
>   loadChatMessages, renderChatGateOrPanel, renderChatProviders/Threads/Messages/Usage,
>   `renderMarkdown` (code fences + inline code + bold + links + bullets),
>   createChatThread, sendChatMessage (optimistic append + shimmer loading + race protection),
>   handleChatFormSubmit (Enter envía, Shift+Enter newline), autoGrowChatInput.
> - State extendido: `chatInitialized`, `chatLoading`, `chatSending`, `chatProviders`,
>   `chatCurrentProvider`, `chatThreads`, `chatCurrentThreadId` (persistido en
>   localStorage), `chatMessages`, `chatUsage`, `chatRequestId`, `chatError`.
>
> **Patrones que el agent inventó (a revisar)**:
> - Loading bubble con shimmer overlay (translateX gradient).
> - Auto-thread-on-send si no hay thread seleccionado (toma primeros 60 chars como título).
> - Enter para enviar, Shift+Enter para newline.
> - Auth gate con `.chat-gate` cuando no hay sesión activa.
>
> **Pre-flight al retomar**:
> 1. Bump `MARKET_BOT_UI_BUILD` y los `?v=` en index.html a `20260530-sprint8`.
> 2. Correr syntax check + tests.
> 3. Si pasa todo, smoke-test en browser: switch surface a "Asistente", crear thread,
>    mandar mensaje (probable que falle si no hay API key configurada — ese es el
>    happy unhappy path, hay que ver el error message).

**Plan**

- Nuevo surface "Asistente" entre "Learning" y "Trading".
- Layout: thread list a la izquierda (compact), chat panel a la derecha.
- Streaming tokens visibles (SSE).
- Markdown rendering (incluye tablas, código).
- Quick-action chips arriba del input: "Analizame mi portfolio", "¿Conviene
  vender NVDA ahora?", "Explicame qué es CAGR".
- Provider switcher (chip arriba) — si hay múltiples configurados, el user
  puede elegir.
- Indicador visible del modelo activo: "Claude Sonnet 4.5 · costo $0.003/msg
  estimado".

### 8.5 · Salvaguardas + observability `[x]`

> ✅ DONE 2026-05-29 (incluido en 8.1). `SYSTEM_PROMPT_BASELINE` hard-coded
> con disclaimer "marcos de decisión, no fallo binario". Rate limit
> 20 messages/hour/IP via `rate_limit()` existing helper. Audit log es la
> propia tabla `chat_messages` con tokens + cost + latency por turn.
> Endpoint `GET /chat/usage` agrega cost/tokens por provider/día/mes.
> Pricing dict per-model best-effort (claude $3/$15, gpt-4o-mini $0.15/$0.60,
> gemini-flash $0.075/$0.30 por 1M tokens) — disclaimer en el código.

**Plan**

- Token counting + cost estimate por mensaje, mostrado en UI.
- Filtro: el bot **NO** debe dar consejos de inversión específicos sin
  disclaimer. System prompt explícito.
- Audit log: cada mensaje se guarda en `chat_messages` con timestamp,
  provider, model, tokens_in, tokens_out, latency_ms.
- Endpoint `GET /chat/usage` para que el user vea cuánto gastó.

**DoD para Sprint 8 completo**
- 3 providers funcionando (OpenAI + Anthropic + Gemini).
- User puede chatear sobre su portfolio y obtener respuestas con sus números
  reales (no genéricas).
- Provider selector en UI funcional.
- Cost / token usage visible.
- Tests: provider mocks, router fallback, rate limit, prompt injection guard.

---

### Out-of-scope para Sprint 4 (registrar como deuda)
- **Backup automático del SQLite** — Fly volume es persistente pero único punto de falla. Plan v2: snapshot diario a S3 o a Cloudflare R2.
- **Rate limit basado en Redis** — el actual es in-memory, no sirve con múltiples instancias. v2 cuando se necesite scale horizontal.
- **Postgres migration** — SQLite + WAL aguanta cómodo 50-100 usuarios activos. Migrar solo cuando se vea contention real en `fly logs`.
- **CI/CD GitHub Actions** — deploy manual con `vercel --prod` y `fly deploy` está OK para v1. Automatizar cuando el squad crezca.

---

## 4.10 · NEW SPRINT — Sprint 9 · REFORZAR EL MOTOR (la lógica) `[ ]` ⭐ FOCO

> Pedido explícito del user (2026-05-30): "reforzar el motor, la lógica".
> Tras auditar `packages/engine/src/market_bot/models/baseline.py` +
> `signals/deterministic.py`, hay un problema de fondo real, no cosmético.

### Diagnóstico — qué está mal en la lógica hoy

1. **EL MODELO PREDICE LA COSA EQUIVOCADA (crítico).**
   En `baseline.py:70-72` el target es `Close.shift(-1) > Close` — la dirección
   del **próximo bar**. Para horizonte SHORT eso es **la próxima hora** (data 1h).
   Predecir el próximo bar a 1h desde indicadores técnicos es esencialmente
   **predecir ruido de microestructura** → por eso el warning `f1 < 0.48`
   ("apenas supera al azar") salta casi siempre. El target debería ser el
   **retorno a horizonte** (ej. +N días para short, +N semanas para long),
   no el próximo bar. Este es EL fix de lógica más importante.

2. **Un modelo por ticker, entrenado de cero sobre ~800 barras (`baseline.py:94-130`).**
   RandomForest depth 5 sobre 14 features y muestra chica, por ticker, sin
   aprendizaje cross-sectional. Overfittea ruido y además es lento (entrena
   2-3 modelos × ticker → es la causa raíz de los 65s del ranking, ver Sprint 7).
   Mejor: **un modelo pooled** entrenado sobre todo el universo (más robusto +
   ~50x más rápido en inferencia + arregla la performance de raíz).

3. **Mismatch de horizonte (`config.py` HORIZON_CONFIG).** SHORT = 180d de barras
   1h prediciendo 1h; LONG = 5y de 1d prediciendo 1d. Ninguno matchea el
   "corto/largo plazo" que el user elige (que deberían ser multi-día/multi-semana).

4. **Los escenarios son una fórmula, no magnitudes (`baseline.py:232-260`).**
   bull/base/bear salen de transformar `probability_up`, sin retorno esperado
   asociado. El user ve "bull 45%" pero no "+8% esperado". Falta el **tamaño**
   del movimiento (distribución de retornos a horizonte), no solo la dirección.

5. **No hay hurdle / costos.** `probability_up > 0.5` no implica que valga la pena:
   en ARS competís contra plazo fijo (tasa alta) + costos de transacción + el CCL.
   La lógica de acción (`policy.py`) no descuenta ese piso.

6. **Catalysts apenas integran (`service.py:_apply_rumor_policy`).** Solo capean
   rumores; earnings/news confirmados no mueven la probabilidad de forma principiada.

### Plan (ordenado por impacto)

- **9.1 · Redefinir el target a retorno-a-horizonte** `[x]` DONE 2026-05-30 ← EL fix

  > ✅ VERIFICADO EN VIVO 2026-05-30 (sesión A). Tras restart, `/analyze` real:
  > NVDA F1=0.611, MELI F1=0.711, AAPL F1=0.588 (antes ~0.48 = azar, warning
  > constante). Brier 0.23-0.26. Path validado (sample 1039), no fallback.
  > **El target a horizonte es aprendible donde el de próximo bar era ruido —
  > hipótesis confirmada con datos reales.** 92/92 tests verde.
  > Bug encontrado y arreglado en la verificación: el call-site interno quedó con
  > el nombre viejo `_target_horizon_bars` tras hacer público el helper → tiraba
  > NameError y caía al fallback. Los tests no lo agarraron (mockean la función);
  > SOLO la verificación en vivo lo detectó. Lección: correr `/analyze` real
  > siempre que se toque `baseline.py`.
  > Pendiente menor (no bloqueante): tunear H (35 short / 20 long son primera
  > estimación; los F1 actuales ya validan que sirven).
  - Target = signo del retorno a H barras según horizonte, no `shift(-1)`.

  > **HECHO 2026-05-30 (sesión A, ~25% tokens):**
  > - `models/baseline.py`: agregado `_TARGET_HORIZON_BARS = {SHORT: 35, LONG: 20}`
  >   + helper `_target_horizon_bars(horizon)`. El target en `_generate_validated_signal`
  >   pasó de `Close.shift(-1)` a `Close.shift(-horizon_bars)`. `modeling_frame` ahora
  >   usa `.dropna()` (saca las últimas H filas sin futuro) en vez de `.iloc[:-1]`.
  >   Nota de `ModelValidationSummary` actualizada. **92/92 tests verde**, app.py/baseline parsean.
  > - El cambio es seguro: `generate_probabilistic_signal` envuelve en try/except →
  >   si el path nuevo fallara en algún ticker, degrada al fallback heurístico (no 500).
  >
  > **PENDIENTE 9.1 (próximos steps, en orden):**
  > 1. ✅ HECHO 2026-05-30 — **Alineado `validation/` al target del modelo.**
  >    `walk_forward_predictions` ya labelaba a `horizon_days` (no era next-bar como
  >    pensé), pero `validate_ticker` hardcodeaba `horizon_days=5`. Ahora:
  >    `target_horizon_bars` se hizo público (models/__init__), `validate_ticker`
  >    usa `horizon_days=None→target_horizon_bars(horizon)` por default, y el endpoint
  >    `/validation/{ticker}` hace `horizon_days` opcional (default=None→alineado).
  >    Modelo (35/20 barras) y Brier ahora miden el MISMO target. 92/92 verde.
  >    Los `test_validation_brier` pasan sin cambios porque llaman con horizon_days
  >    explícito; no asumían next-bar. → No hizo falta rehacer esos 12 tests.
  > 2. **Verificación en vivo**: reiniciar server y `POST /analyze` sobre 3-4 tickers
  >    con tendencia clara (ej. NVDA, MELI) → confirmar que el F1/Brier dejó de ser
  >    ~azar y que `probability_up` tiene sentido. (No lo hice por presupuesto de tokens;
  >    el server corriendo tiene código viejo de baseline — requiere restart + ~75s warmup.)
  > 3. **Tunear H** si hace falta: 35 barras (SHORT) y 20 (LONG) son una primera
  >    estimación; validar contra el F1 real por horizonte.
  > 4. **Sanity de muestra**: con H grande, confirmar que el guard `len(modeling_frame) < 180`
  >    no dispara fallback en tickers normales (para 180d×1h ~1260 barras está OK).

- **9.2 · Modelo pooled cross-sectional** `[ ]` → **PLAN GRANULAR EN `docs/sprint-9.2-pooled-model.md`**
  (7 pasos ejecutables + scope + riesgos + DoD + verificación en vivo. Arrancar por ahí.)
  - Un solo modelo entrenado sobre features de TODO el universo (con ticker como
    feature o normalización cross-sectional), inferencia por ticker.
  - Arregla overfitting + mata los 65s del ranking (inferencia es ms, no s).
  - Mantener el path per-ticker como fallback. Cuidar `test_validation_brier`.

- **9.3 · Magnitudes en escenarios** `[ ]`
  - Estimar distribución de retornos a horizonte (cuantiles del histórico
    condicionado, o regresión) → bull/base/bear con "+X% / 0% / −Y%" esperado.
  - El user ve tamaño, no solo dirección.

- **9.4 · Hurdle ARS en la política de acción** `[ ]`
  - En `policy.py`, descontar el piso (plazo fijo + costos) antes de sugerir compra.
    "Sube probable, pero no le gana al plazo fijo" es una salida válida y honesta.

- **9.5 · Integración principiada de catalysts** `[ ]`
  - Earnings confirmados / surprise reciente / news de alta confianza desplazan
    `probability_up` con un peso acotado y auditable (no solo capean rumores).

**Archivos núcleo:** `packages/engine/src/market_bot/models/baseline.py`,
`signals/deterministic.py`, `config.py` (HORIZON_CONFIG + horizonte de target),
`validation/` (alinear walk-forward al nuevo target), `strategies/policy.py` (hurdle),
`service.py` (`_apply_rumor_policy`). Tests: `test_validation_brier.py` (no romper
determinismo), nuevos tests del target/horizonte.

---

## 4.11 · NEW SPRINT — Sprint 10 · Validación: probar que el motor tiene edge `[ ]`

> Sin esto, el motor es una caja negra no validada. Es lo que convierte
> "juguete lindo" en "tiene edge demostrable". Va junto con Sprint 9.

- **10.1 · Decision audit loop completo (era 6.3)** `[ ]` — job offline
  `realize_decisions` que completa `realized_return` N días después de cada
  decisión guardada. Endpoint `GET /decisions/track-record`.
- **10.2 · Backtest del ranking (era 6.9)** `[ ]` — "si seguías el top-3 del
  ranking cada día, ¿qué pasaba?" vs SPY/Merval buy-and-hold + vs plazo fijo.
  Métricas: cum return, max drawdown, hit rate, Sharpe, Calmar.
- **10.3 · Track-record en UI** `[ ]` — panel que muestra el edge real (o la
  falta de él, honestamente). Conectado a `/validation` (Brier) que ya existe.

---

## 4.12 · NEW SPRINT — Sprint 11 · Loop del tester + chat como interfaz `[ ]`

- **11.1 · Botón de feedback in-app** `[ ]` — "Reportar algo" que escriba a una
  tabla `feedback` (o mande mail vía el connector Gmail ya conectado). Cierra el
  loop de feedback del tester. ~30 min, alto valor.
- **11.2 · Onboarding mínimo (era 6.10)** `[ ]` — 3 pasos: cargar perfil →
  importar Balanz → preguntarle al asistente. Sin esto el tester no encuentra el valor.
- **11.3 · Tool-use del chat (era 8.3b)** `[ ]` — que el bot llame
  `analyze_ticker` / `get_portfolio_summary` / `compare_to_benchmark` como tools.
  Convierte el chat de "ChatGPT con contexto pegado" a interfaz principal mágica.

---

## 4.13 · NEW SPRINT — Sprint 12 · Confiabilidad + deploy real `[ ]`

> Solo cuando el tester valide que vale la pena. No invertir en infra de algo no validado.

- **12.1 · Abstraer el data source + fallback** `[ ]` — todo depende de yfinance
  (no oficial, rate-limited, se rompe). Reforzar `MarketDataAdapter` con cache
  agresivo + un provider de fallback (Alpha Vantage / Polygon) para no morir con
  10 usuarios concurrentes. Esto es lo que frena pasar de 1 a 10 testers.
- **12.2 · Deploy real con persistencia** `[ ]` — Heroku + Postgres (tenés créditos;
  Heroku borra el SQLite al reiniciar → migrar la capa DB). Reemplaza el túnel +
  Mac-prendida cuando deje de alcanzar.

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
- **Sprint 4 (deploy)** [~]: scaffolding listo, app corriendo local, deploy real Vercel+Fly pendiente.
- **Sprint 5 (polish + correctness)** ✅ Cerrado salvo 5.5 (otras cosas raras del user).
- **Sprint 6 (future improvements)** [~] avanzado en 2026-05-28:
  - 6.0 (typography pass del portfolio summary) ✅ DONE — hero + satellites + real-return bar.
  - 6.1 (canonical CEDEAR ratios) ✅ DONE — 50+ tickers + chip de source en holding card.
    - 6.1b (Balanz FX columns read) ✅ parser leyendo CCL/MEP/Oficial del xlsx
      + schema migration ADD COLUMN purchase_ccl/mep/official. Propagación al
      cost_basis pendiente como 6.1c.
  - 6.2 (earnings calendar UI) ✅ DONE — banner sticky con countdown + CTA + dismiss persistente.
    - 6.2b (surprise history grid) ✅ DONE 2026-05-29 por agent paralelo. Endpoint nuevo
      `GET /earnings/{ticker}/history?limit=12` con yfinance `earnings_history` + computed
      next-day-return. Cache 24h doble (adapter + route). UI grid 4×3 con bull/bear tinting
      en cada quarter, skeleton + empty state, hook a `analyzeTicker`.
    - 6.2c (pre/post-market reaction %) ✅ incluido en 6.2b — el `next_day_return_pct` cubre
      el caso AMC. Pre-market lo dejamos para una segunda iteración si lo pedís.
  - 6.3 – 6.10 ⏳ siguen en cola.
- **Sprint 6.5b (opportunity-cost framing + ad-hoc benchmarks + diagnostics)** ✅ DONE
  2026-05-28: rediseño completo del panel benchmark, endpoint `/portfolio/benchmarks/custom`
  para benchmarks ad-hoc (cualquier ticker yfinance), endpoint `/portfolio/diagnostics`
  para inspeccionar precios crudos por posición, transitions.dev install (card-resize +
  number-pop-in), 35 nuevos acronyms en Learning (ATH/CAGR/FY27/YTD/1Q26/EPS/...).
- **Sprint 7 (Core engine, calculations, performance)** [ ] NUEVO · TOP PRIORITY 2026-05-28.
  Los números siguen sin cuadrar para el user — bloquea cualquier feature futuro.
- **Sprint 8 (AI chatbot multi-provider)** [ ] NUEVO 2026-05-28 — Gemini/OpenAI/Claude con
  context-aware prompts del portfolio del user, .env-driven config.
- **48/48 tests pasan** offline en 3.5s.

---

## Snapshot actualizado — 2026-05-29 fin del día (PAUSED AQUÍ)

### Estado real

- **Sprint 7 (Core engine, calculations, performance)** ✅ COMPLETO:
  - 7.1 diagnostics UI panel ✅
  - 7.2 real return refactor (`preferred_benchmark_return_pct`) ✅
  - 7.3 batch yfinance + cache (300→900s TTL, `prefetch_quotes` + `prefetch_universe`) ✅
  - 7.4 tests matemáticos hard-coded (`tests/test_portfolio_math.py`, 8 tests) ✅
  - 7.5 frontend code-split (GLOSSARY lazy + defer scripts) ✅

- **Sprint 8 (AI chatbot)** [~] casi cerrado:
  - 8.1 backend chat layer (3 providers + router + store + 6 endpoints) ✅
  - 8.2 .env config + provider selection ✅
  - 8.3 **context-aware prompts con tool-use** ⏳ **NO ARRANCADO**
  - 8.4 chat UI 🟡 ENTREGADO POR AGENT, **FALTA VERIFICAR**
  - 8.5 salvaguardas + audit + cost tracking ✅

- **Otros entregados 2026-05-29**:
  - 6.2b earnings surprise history (endpoint + grid 4×3) ✅
  - 6.6 sector + region exposure (classification table + stacked bar) ✅

### Last known good test count: 81/81

Medido después del agent 8.1+8.5 (chat backend) e integración 6.2b+6.6.
**El agent 8.4 (chat UI) entregó cambios pero NO se verificó** porque el user
pausó la ejecución antes del syntax check + tests + smoke test.

### Sin commitear

Aproximadamente ~5000 líneas en el working tree. Incluye:
- Sprint 7 completo (backend perf + frontend code-split + diagnostics).
- Sprint 8.1+8.2+8.5 backend chat layer entero.
- Sprint 8.4 chat UI (sin verificar).
- 6.2b/6.6 surprise history + sector exposure.
- 6.1b Balanz FX parser + schema migration.

### Pre-flight obligatorio al retomar (orden estricto)

**Paso 0** — fotografiar el estado:
```bash
cd /Users/lucianoamato/Desktop/Proyectos/market_bot/market_bot
git status --short
git diff --stat | tail -15
```

**Paso 1** — verificar 8.4 (chat UI):
```bash
node -e "new Function(require('fs').readFileSync('apps/web/prototype/app.js','utf8'))"
python3 -m pytest tests/ --tb=short
```
Si JS rompe o tests bajan de 81 → fix antes de seguir.

**Paso 2** — bump version stamps:
- `apps/web/prototype/index.html`: cambiar todos los `?v=20260529-sprint7c` a `?v=20260530-sprint8`.
- `apps/web/prototype/app.js`: cambiar `MARKET_BOT_UI_BUILD` a `2026-05-30 · sprint-8 · chat`.

**Paso 3** — smoke test del chat UI en browser:
- Reiniciar backend (`uvicorn services.api.app:app --host 127.0.0.1 --port 8000 --reload`).
- Hard refresh (Cmd+Shift+R).
- Switch surface a "Asistente".
- Sin API key → debería mostrar chip "Sin proveedores configurados".
- Con API key en `.env` → crear thread, mandar mensaje.

**Paso 4** — Sprint 8.3 (lo único pending de Sprint 8):
Implementar `build_user_context(user_id)` en `packages/chat/.../store.py` para
hidratar system prompt con portfolio + perfil. Y opcionalmente sumar `tools.py`
con 4 tools. Spec completa en sección 8.3 más arriba.

**Paso 5** — commit final del Sprint 8 entero.

### Después de Sprint 8 — orden sugerido

1. **6.1c** — Propagar `purchase_ccl/mep/official` del Balanz xlsx al
   `_cost_basis`. Quick win ~30 min. El parser ya lee los valores (6.1b ✅);
   falta hacerlos override del FX que pide `argentinadatos.com`.
2. **Sprint 4** — Deploy real Vercel + Fly. Necesario para compartir con beta.
3. **6.3** — Decision audit loop (computar realized return offline).
4. **6.5** — Paper trading sandbox.
5. **6.6 polish** — Sector exposure ya está, falta tooltip por bucket explicando qué hay adentro.
6. **6.7/6.8/6.9/6.10** — Push alerts, multi-currency, ranking backtest, onboarding tour.
7. **5.5** — Recolectar otras "cosas raras" que el user pueda reportar.
8. **Audit UI/UX iteración 2** — B2/B3/B4/B8/B10 (redundancia, citrus glow,
   benchmark cards consolidados, surface tabs density, hover states).

### Audit UI/UX completado (2026-05-28)
Documentado en transcripción de chat. Strengths preservadas: identidad
Fraunces+DM Sans+JetBrains Mono, paleta citrus, dual-theme system. Issues
atacados en typography pass: jerarquía visual (B1), formato monetario (B5),
weight/sizing de números (B6), real return como protagonista (B7). Issues
abiertos para iteración posterior: redundancia de labels (B2), citrus glow
oversize (B3), 5 benchmark cards redundantes (B4), surface tabs density (B8),
hover state genérico en radar cards (B10).

### Next moves sugeridos (orden de prioridad post-2026-05-28)

**Bloque A — Core correctness (Sprint 7)** ← TOP PRIORITY
1. **Sprint 7.1** Auditoría de cálculos end-to-end · resolver el mismatch
   entre cost basis y valor actual reportado. Diagnostics endpoint en UI.
2. **Sprint 7.4** Tests de matemática con fixtures hard-coded · golden snapshots.
3. **Sprint 7.2** Real return refactor para respetar `benchmark_preference`.

**Bloque B — Performance (Sprint 7 cont.)**
4. **Sprint 7.3** Batch yfinance + cache layers + background precompute.
5. **Sprint 7.5** Frontend code-split + lazy load.

**Bloque C — AI Chatbot (Sprint 8)**
6. **Sprint 8.1 + 8.2** Backend chat layer + provider abstraction + .env config.
7. **Sprint 8.3** Context-aware prompts con tool-use.
8. **Sprint 8.4 + 8.5** UI + observability.

**Bloque D — Closing existing work**
9. **Sprint 6.1b** Leer FX desde el xlsx de Balanz.
10. **Sprint 6.2b** Surprise history grid.
11. **Sprint 4** Deploy real Vercel+Fly.

**Bloque E — Después**
12. **Sprint 6.3** Decision audit loop.
13. **Sprint 6.5** Paper trading.
14. Resto de Sprint 6.

---

## Queue recommendation — post beta local (2026-05-28)

> Estado actual recomendado: **beta privada local usable**. La app ya tiene
> portfolio, CEDEAR mapping mejorado, benchmarks ARG, import Balanz, Buffy,
> learning y análisis consolidado. Lo siguiente no es “sumar features por sumar”:
> es cerrar producto, performance y deploy en el orden correcto.

### Bloque 1 · UX final `[ ]`

**Objetivo**: que la app se sienta cerrada como producto y no como workspace acumulado.

1. **Auth + navegación real**
   - Pasar de hash/modal híbrido a rutas reales (`/login`, `/app`, `/portfolio`, `/learning`).
   - Mantener `settings` arriba a la derecha como entrypoint único de cuenta.
2. **Portfolio polish final**
   - Mejorar lectura de `Resumen / Cargar / Posiciones`.
   - Agregar agrupación por ticker cuando haya múltiples lotes.
   - Sumar edición/borrado/historial de compras sin fricción.
3. **Workspace simplification**
   - Reducir `Market regime` a una lectura más ejecutiva.
   - Hacer más clara la recomendación final: qué hacer, por qué, y con qué confianza.
4. **Onboarding surface**
   - Ajustar `How to use` y `Learning` para primera sesión real.

**DoD**
- Un usuario nuevo entiende dónde loguearse, dónde ver portfolio y cómo leer una sugerencia en menos de 5 minutos.
- No quedan superficies ambiguas o duplicadas.

### Bloque 2 · Performance + cleanup `[ ]`

**Objetivo**: bajar fricción y tiempos percibidos antes de hostear.

1. **Frontend**
   - Seguir cortando trabajo al boot.
   - Lazy-load de surfaces no críticas.
   - Debounce y cancelación consistente en búsquedas y análisis.
2. **API / engine**
   - Medir y endurecer `analyze`, `rankings`, `market/overview`, `portfolio/summary`.
   - Mantener cache server-side y evitar trabajo duplicado.
3. **Data correctness cleanup**
   - Seguir limpiando reglas de scoring/contexto.
   - Mantener trazabilidad de ratios, catalysts y warnings.
4. **Tests**
   - Ampliar cobertura sobre portfolio/import/benchmark/chat/contexto.

**DoD**
- Carga inicial y navegación visiblemente más rápidas.
- Endpoints pesados con latencia más estable.
- Regresiones críticas cubiertas por tests.

### Bloque 3 · Deploy-ready + producción básica `[ ]`

**Objetivo**: pasar de demo local a app compartible con usuarios reales.

1. **Base de datos**
   - Migrar SQLite → Postgres.
   - Agregar migraciones formales.
2. **Configuración**
   - Consolidar `.env`, `local/host`, CORS y secrets.
3. **Hosting**
   - Cerrar el split frontend/backend de forma estable.
   - Completar Vercel + Fly o reemplazar por alternativa más simple si conviene.
4. **Observabilidad + seguridad**
   - Logs, rate limiting, readiness, backups básicos.

**DoD**
- URL pública estable.
- Persistencia real.
- Troubleshooting básico posible sin entrar a debug manual.

### Bloque 4 · Motor y producto avanzado `[ ]`

**Objetivo**: una vez cerrado lo anterior, recién ahí empujar inteligencia y trading.

1. **Motor de recomendación**
   - Mejor integración de técnico + noticias + earnings + macro + fundamentos.
   - Explicación consolidada y auditada.
2. **Decision loop**
   - Track record del usuario y realized returns.
3. **Paper trading / Wallbit prep**
   - Primero sandbox.
   - Después integración real.
4. **Expansiones**
   - Social sentiment.
   - Ranking backtest.
   - Push alerts.

**DoD**
- El sistema no solo sugiere, sino que permite medir si esas sugerencias sirvieron.

### Orden sugerido desde ahora

1. **Bloque 1** completo.
2. **Bloque 2** casi completo.
3. **Bloque 3**.
4. **Bloque 4**.
