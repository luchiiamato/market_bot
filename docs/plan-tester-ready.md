# Plan — Tester-ready polish (2026-05-30)

## DECISIÓN 2026-05-30 · Fast-path ML (1A.3) → NO. Alternativa elegida abajo.

**Rechazado el fast-path `light=True` (1 RF × 40 árboles sin calibración para ranking).**
Razones:
1. **Divergencia de números** — el ranking mostraría una convicción/probabilidad
   distinta a la que muestra el análisis individual del MISMO ticker (modelos
   distintos). Para un tester evaluando si confiar en la herramienta, ver "55%"
   en la card y "61%" al abrirla erosiona la confianza. El #1 del ranking podría
   verse mediocre al abrirlo. Trust > 50s ahorrados en un caso de borde.
2. **Optimiza un modelo que predice la cosa equivocada** — Sprint 9.1 ya
   estableció que el target (próximo bar, ruido) está mal. Acelerar un modelo
   defectuoso es esfuerzo tirado + deuda técnica que hay que desarmar después.
3. **El warmup ya cubre el caso común del tester** (rankings default short+long
   + top-10 análisis, cada 8 min). El único hueco frío real es `mode=opportunities`.

**Alternativa elegida (hacer AHORA, barata, sin riesgo, sin divergencia):**
- **Extender `_warm_rankings_cache`** (app.py) para que ADEMÁS warmee
  `mode="opportunities"` en short+long. Cierra el último path frío del tester
  con 2 líneas, sin tocar el modelo, sin divergencia, sin riesgo en Brier tests.
- (Opcional) subir el top-N de tickers pre-analizados de 10 a ~15.

**El speedup real va a Sprint 9.2 (modelo pooled)** — inferencia en ms para TODOS
los tickers, sin divergencia (un solo modelo), más robusto. Eso resuelve velocidad
Y la lógica de una. Es donde va el esfuerzo, no en un band-aid descartable.

### ✅ HECHO 2026-05-30 (sesión A) — warmup extendido a opportunities

`services/api/app.py::_warm_rankings_cache` ahora warmea ambos modos
(`default` + `opportunities`) × ambos horizontes. Verificado en vivo:
- `short/default` cold = 73.9s (lo de siempre, corre en background al boot).
- `short/opportunities` = **1.5s incremental** (reusa el cache de analyze_ticker).
- Endpoints ya cacheados responden en ~10-24ms.

→ El tester ya no pega ningún path frío de ranking (default ni opportunities,
short ni long) ni de análisis de los top-10 tickers. **92/92 tests verde.**
Cambio backend-only (no toca frontend → no hace falta bump de cache-buster).

---

## COORDINACIÓN ENTRE SESIONES (2026-05-30)

Hay DOS sesiones trabajando este repo. Para no pisarse:

- **Sesión A (esta)** tocó SOLO `services/api/app.py` (`_warm_rankings_cache`).
  Sin commitear. Dejó los fixes previos (Gemini, ratios, FX parser) ya en disco.
- **Sesión B** está ejecutando el plan `~/.claude/plans/...mccarthy.md`:
  Bloque 1B (UX de espera + skeletons + 7.6), Bloque 2 (mobile), Bloque 3 (FX cost_basis).
  Toca `app.js`, `styles.css`, `index.html`, `portfolio/service.py`.

**No hay colisión** entre lo de A (app.py warmup) y B (frontend + portfolio).

## NEXT STEPS — dónde seguir (orden)

1. **(Sesión B, en curso)** Terminar Bloque 1B + 2 + 3 del plan tester-ready.
2. **Verificación conjunta**: cuando B termine, correr `pytest` (mantener ≥92),
   syntax check de app.js, restart server + probar en el túnel desde celular real.
3. **Sprint 9 — REFORZAR EL MOTOR** (lo que más mueve la aguja, ver work-queue 4.10):
   - 9.1 target a horizonte (no próximo bar) ← el fix de lógica #1.
   - 9.2 modelo pooled (resuelve velocidad de raíz Y robustez; reemplaza para siempre
     la necesidad de cualquier fast-path).
   - 9.3 magnitudes en escenarios · 9.4 hurdle ARS · 9.5 catalysts principiados.
4. **Sprint 10 — Validación** (probar edge): decision audit loop + backtest del ranking.
5. **Sprint 11 — tester loop**: botón feedback + onboarding + tool-use del chat.
6. **Sprint 12 — confiabilidad/deploy**: abstraer data source + Heroku+Postgres.

> Regla: Sprint 9.2 (modelo pooled) es el verdadero reemplazo del fast-path
> rechazado. Cuando se haga, la velocidad del ranking deja de ser un problema
> para siempre, sin band-aids.

---


> Objetivo: que un tester externo (vía túnel cloudflared) tenga una experiencia
> pulida, sin fricción, en desktop Y celular. Priorizado: primero lo que el
> tester ve y toca, después correctness, después backlog.

---

## BLOQUE 1 — UX crítica para el tester (HACER PRIMERO)

### Step 1.1 · Mobile responsive pass  ← fix pedido por el user ("desde el celular se ve muy feo")

**Diagnóstico:** hay CSS responsive (16 media queries) pero los componentes nuevos
(chat, opportunity-cost, diagnostics, exposure) tienen cobertura despareja.
Quiebres probables en ≤390px:

- **Diagnostics table** (9 columnas) — inusable en celular. Fix: en mobile,
  convertir cada fila a card apilada (label arriba, valor abajo) o scroll-x con
  sticky first column.
- **Chat layout** (2 columnas thread-list + conversación) — verificar que apile
  y la thread-list sea colapsable/horizontal, no que aplaste el chat.
- **Opportunity rows** (`grid-template-columns` de 5) — el número grande puede
  desbordar; verificar el reflow del `@media 720`.
- **Portfolio hero summary** — el número gigante con `clamp()` no debe cortarse;
  satellites apilados.
- **Surface tabs / portfolio view tabs** — scroll horizontal OK pero verificar
  que no tape contenido.
- **Touch targets** — botones/pills ≥ 44px; verificar tap highlight.
- **Headings** — bajar tamaños que desbordan en 360-390px.

**Pasos:**
1. Levantar el server local y revisar cada surface a 390px y 360px
   (workspace, portfolio [resumen/cargar/posiciones/diagnóstico], learning, chat, acceso).
2. Arreglar cada quiebre con media queries focalizadas (preferir las breakpoints
   existentes 720/480; agregar 390 si hace falta).
3. Diagnostics table → card-layout en mobile (el más roto).
4. Verificar overflow horizontal global (nada que haga scroll-x la página entera).

**Archivos:** `apps/web/prototype/styles.css` (mayormente), puntualmente
`index.html`/`app.js` si un componente necesita markup extra para el card-layout mobile.

**DoD:** abrir el túnel desde un celular real (o devtools a 390px) y que workspace,
portfolio (incl. diagnóstico) y chat se vean prolijos, sin overflow ni texto cortado.

### Step 1.2 · Tarea 7.6 — feedback del análisis (lo que pediste antes)

Cuando se toca "Analizar setup", hoy no hay feedback claro de cuándo termina.

**Pasos:**
1. **Estados de progreso**: botón → "Analizando…" deshabilitado (anti doble-submit);
   status line → "Analizando {TICKER}… (el primer análisis es el más lento; los
   próximos son instantáneos por cache)".
2. **Skeleton del verdict** (no spinner pelado): placeholders con la forma del
   verdict card para que el layout no salte.
3. **Toast de finalización** "✓ Análisis de {TICKER} listo" usando la transición
   success-check de transitions.dev (tokens `--check-*` ya instalados) + scroll
   suave al verdict.
4. **Notification API** si la pestaña está en background (pedir permiso 1ª vez;
   degradar silenciosamente al toast si lo deniegan).
5. **Cache-hit** (<~400ms): directo al resultado, sin flujo de espera ni toast.

**Archivos:** `app.js` (`analyzeTicker`, `setButtonBusy`, `setStatus`),
`styles.css` (`.analysis-toast`, skeleton del verdict), `index.html` (contenedor toast).

**DoD:** analizar un ticker en el túnel → siempre sabés arrancó/sigue/terminó;
aviso claro al terminar; sin doble-submit; sin salto de layout.

---

## BLOQUE 2 — Correctness loose ends (MEDIA)

### Step 2.1 · 6.1c — propagar FX del Balanz al cost_basis

El parser ya lee `purchase_ccl/mep/oficial` del xlsx (6.1b ✅) y la columna existe
en la DB, pero `_cost_basis` sigue pidiendo el FX a argentinadatos.com (que falla
para fechas viejas → cost_basis_usd inconsistente).

**Pasos:**
1. En `_cost_basis` (o `_build_position_valuation`), si la posición tiene
   `purchase_ccl` guardado, usarlo como override del FX de compra en vez de pedirlo
   a la API externa.
2. Persistir esos campos en `add_position`/import (hoy se parsean pero verificar
   que se guarden en la fila).
3. Test con fixture: posición con purchase_ccl seteado → cost_basis_usd usa ese FX.

**Archivos:** `packages/portfolio/src/market_portfolio/service.py`, `balanz.py`
(asegurar que el import pase los campos), `tests/test_portfolio_math.py`.

**DoD:** posiciones importadas de Balanz nunca dependen de argentinadatos.com para
el FX de compra; test que lo fija.

---

## BLOQUE 3 — Polish visual remanente del audit UI (MEDIA-BAJA)

### Step 3.1 · B2/B3 del audit
- **B2**: barrer labels redundantes restantes (kicker + heading + caption que repiten).
- **B3**: el glow citrus del bloque "MI PORTFOLIO" / opportunity-origin — verificar
  que no desperdicie espacio; si sigue grande, meterle una sparkline o achicar.

**Archivos:** `index.html`, `styles.css`.

---

## BLOQUE 4 — Acceso permanente (BAJA para hoy; el túnel ya cubre al tester)

### Step 4.1 · (opcional) Heroku con Postgres
Solo si querés algo que no dependa de tu Mac. Heroku borra el SQLite al reiniciar
→ requiere migrar a Heroku Postgres (add-on + capa de DB). Es un mini-sprint aparte.
Por ahora el túnel alcanza. Lo dejo documentado, no lo ejecuto salvo que lo pidas.

---

## BACKLOG (no en esta tanda)
8.3b tool-use del chat · 6.3 decision audit loop · 6.5 paper trading ·
6.7 push alerts · 6.8 multi-currency · 6.9 backtest del ranking ·
6.10 onboarding tour · 5.5 surface audit de cosas raras.

---

## Orden de ejecución recomendado
1. **Step 1.1 (mobile)** — lo que más se nota y lo pediste explícito.
2. **Step 1.2 (7.6 análisis UX)** — segundo más visible para el tester.
3. **Step 2.1 (6.1c FX)** — correctness, rápido.
4. **Step 3.1 (polish B2/B3)** — si queda tiempo.
5. Bloque 4 / backlog — bajo demanda.

Después de cada bloque: correr `python3 -m pytest tests/` (mantener 91/91) +
`node -e "new Function(...app.js)"` syntax check + bump del cache-buster, y
probar en el túnel.
