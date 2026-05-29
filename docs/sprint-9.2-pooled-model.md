# Sprint 9.2 — Modelo pooled cross-sectional (plan granular)

> Estado: 9.1 ✅ (target a horizonte, verificado: F1 0.59-0.71 en vivo).
> 9.2 NO arrancada — necesita presupuesto fresco. Este doc es la receta ejecutable.

## Objetivo y por qué

Hoy `baseline.py::_generate_validated_signal` entrena **2-3 RandomForest +
CalibratedClassifierCV POR TICKER** sobre ~800-1039 barras, en cada `analyze_ticker`.
Problemas:
- **Lento**: ~400-600ms × ticker → es la causa raíz de los 65s del ranking (60 tickers).
- **Overfittea**: muestra chica por ticker, sin aprendizaje cross-sectional.

**Solución**: entrenar **UN modelo** sobre las features de TODO el universo (pooled),
cachearlo, e inferir por ticker en milisegundos. Más robusto (más datos, patrones
compartidos) y ~50x más rápido en el path de análisis/ranking.

Reutiliza lo de 9.1: el target a horizonte (`target_horizon_bars`) y el
`_build_feature_frame` que ya existe en `baseline.py`.

## Decisión de scope (importante, reduce riesgo)

- **El modelo pooled reemplaza el entrenamiento per-ticker SOLO en el fast path**
  (`analyze_ticker` → `probability_up` + ranking).
- **`/validation/{ticker}` (walk-forward Brier) SE QUEDA per-ticker** — es la
  herramienta de "track record honesto", corre on-demand, lentitud aceptable.
  Esto evita tocar `validation/brier.py` y **deja los 12 `test_validation_brier`
  intactos**. No los rompas.
- Mantener `generate_probabilistic_signal` (per-ticker) como **fallback** cuando
  el modelo pooled no esté listo (arranque frío, error de entrenamiento).

## Archivos

- **NUEVO** `packages/engine/src/market_bot/models/pooled.py` — entrenamiento +
  inferencia + artifact.
- `packages/engine/src/market_bot/models/__init__.py` — exportar lo nuevo.
- `packages/engine/src/market_bot/service.py` — cachear el artifact por horizonte;
  usarlo en `analyze_ticker`; fallback al per-ticker.
- `services/api/app.py` — entrenar el pooled en el warmup de startup (ya existe
  `_warm_rankings_cache`).
- `tests/test_pooled_model.py` — NUEVO, offline con frames sintéticos.

## ESTADO 2026-05-30 (noche): INFRA COMPLETA + VERIFICADO EN VIVO. Pooled GATEADO OFF.

**Resultado honesto de la verificación en vivo (la lección de 9.1 pagó):**
- El pooled entrena OK (58 tickers, ~44s, en el warmup). PERO **f1 holdout ≈ 0.417**
  — peor que azar y peor que el per-ticker (0.58-0.71). Shippearlo sería una
  regresión de calidad (prob_up washed out ~0.5, conf en el piso).
- **Decisión: QUALITY GATE.** `service.MIN_POOLED_F1 = 0.52`. `_probabilistic_for`
  usa el pooled SOLO si `artifact.validation.f1 >= 0.52`; si no, cae al per-ticker.
  Verificado en vivo: con el pooled en 0.417, `/analyze` NVDA cae a per-ticker
  (`split=chronological_holdout...`, f1=0.579, conf=0.55). Correctness protegida.
- **Consecuencia:** el speed win (65s→rápido) NO se materializa todavía, porque el
  pooled está gateado off → ranking/analyze siguen usando per-ticker. El warmup
  ya mitiga la lentitud para el tester (sin cambios para él).
- **Infra lista para cuando el pooled mejore**: apenas un pooled cruce f1≥0.52, el
  gate lo deja pasar automáticamente y el speed win arranca solo, sin más wiring.

### → 9.2b (NUEVO): mejorar el pooled para que cruce el gate y entregue el speed
Por qué el pooled simple falla y qué probar (en orden de probable impacto):
1. **Normalización per-ticker de features** — pooled mezcla escalas/regímenes de 58
   tickers. Normalizar cada feature por ticker (z-score rolling) antes de poolear.
2. **Walk-forward CV en vez de un solo time-holdout** — el holdout único cae en una
   ventana reciente que puede ser chop market-wide → f1 bajo. Validar con varios cortes.
3. **Target/threshold**: probar magnitud (retorno > umbral) en vez de pura dirección;
   o target cross-sectional (¿este ticker supera a la mediana del universo a H?).
4. **Más/mejores features** — agregar contexto macro (régimen del SPY/VIX) como columnas.
5. Re-medir f1 holdout; objetivo ≥0.55 para superar cómodo el gate y al per-ticker.

## ESTADO 2026-05-30 (tarde): Pasos 1-7 HECHOS ✅ — verificación en vivo abajo

- Paso 1-4 ✅ `models/pooled.py` (artifact, build_dataset, train con split temporal, predict).
- Paso 5 ✅ `service.py`: `_pooled_cache` (TTL 6h) + lock, `ensure_pooled_artifact`,
  `_get_cached_pooled`, `_probabilistic_for` (pooled-cuando-cacheado, fallback per-ticker).
  `analyze_ticker` usa el helper. NUNCA bloquea en training; degrada en cualquier error.
- Paso 6 ✅ `app.py` warmup: entrena el pooled por horizonte ANTES de los rankings
  (log "pooled train done" con f1/n_tickers). Ahí mueren los 65s del ranking.
- Paso 7 ✅ `tests/test_pooled_model.py` (4 tests offline, sintéticos): dataset/target,
  train+split sin leakage, predict válido, horizonte por plazo. **96/96 tests verde.**

**PENDIENTE — VERIFICACIÓN EN VIVO (la lección de 9.1, NO saltear):**
> Diferida a propósito: hay agents (13.1 backend, 13.2/13.3 frontend) escribiendo
> archivos que el server importa. Reiniciar con un archivo a medio escribir daría
> un fallo espurio. Hacer DESPUÉS de que los agents terminen:
> 1. `source .env` + restart uvicorn (asyncio/h11), esperar log "pooled train done".
> 2. `POST /analyze` NVDA/MELI/AAPL → confirmar `split=pooled_cross_sectional_time_holdout`
>    (NO fallback, NO per-ticker). Si dice fallback, el pooled tiró excepción → debuggear.
> 3. `curl -w %{time_total}` a `/rankings?horizon=short` cold → debería bajar de ~65s
>    a pocos segundos (el grueso pasa a ser el fetch yfinance batch, no el ML).
> 4. `pytest` ≥96 verde.

---

## ESTADO PREVIO: Pasos 1-4 SCAFFOLDED (referencia)

`packages/engine/src/market_bot/models/pooled.py` ya creado y exportado en
`models/__init__.py`. Contiene `PooledArtifact`, `build_pooled_dataset`,
`train_pooled_model` (split temporal por fecha), `predict_pooled` y
`_pooled_dominant_features`. Reusa `_build_feature_frame`/`_scenarios`/`_confidence`/
`target_horizon_bars` de baseline (sin refactor). Importa OK, 92/92 tests verde.
**Falta**: Paso 5 (cachear en service + usar en `analyze_ticker` con fallback),
Paso 6 (entrenar en el warmup), Paso 7 (tests offline `test_pooled_model.py`),
y la VERIFICACIÓN EN VIVO (la lección de 9.1: `/analyze` real, no solo tests).

## Pasos granulares

### Paso 1 · `pooled.py` — estructura
```python
@dataclass
class PooledArtifact:
    model: object                  # CalibratedClassifierCV entrenado
    feature_columns: list[str]
    horizon: Horizon
    validation: ModelValidationSummary  # métricas GLOBALES del holdout
    trained_at: datetime
    n_tickers: int
    n_samples: int
```

### Paso 2 · `build_pooled_dataset(adapter, universe, horizon)`
- Para cada ticker del `universe`: `adapter.get_price_history` → `compute_indicators`
  → reutilizar `_build_feature_frame` (de baseline.py — exportarlo o moverlo a un
  módulo `features.py` compartido) → construir target con `target_horizon_bars(horizon)`
  (`Close.shift(-H) > Close`), dropna las últimas H filas.
- **Agregar columna `__date`** (timestamp del row) y opcionalmente `__ticker` para
  el split temporal. NO usar ticker como feature de entrada al modelo en v1
  (evita que aprenda "MELI siempre sube"); sí para auditar.
- Concatenar todos en un X, y global. Soft-fail por ticker (si uno falla, skip + log).

### Paso 3 · `train_pooled_model(...)` → `PooledArtifact`
- **Split TEMPORAL por fecha, NO por row** (evita leakage cross-ticker): ordenar por
  `__date`, usar el último ~20% del rango de FECHAS como test, el resto train.
  (Un split por row mezclaría futuro de un ticker con pasado de otro.)
- Entrenar `CalibratedClassifierCV(RandomForestClassifier(n_estimators=200, max_depth=6,
  min_samples_leaf=20, class_weight="balanced_subsample"), method="sigmoid", cv=3)`
  UNA vez sobre el train pooled. (Podés subir n_estimators porque es 1 sola vez.)
- Métricas globales en el test (accuracy/precision/recall/f1/brier) → `ModelValidationSummary`
  con `split_strategy="pooled_cross_sectional_time_holdout"`.
- Guardar `feature_columns` = orden exacto de columnas para inferencia consistente.

### Paso 4 · `predict_pooled(artifact, current_features) -> ProbabilisticSignal`
- `current_features` = última fila del feature_frame del ticker (reindex a
  `artifact.feature_columns`).
- `probability_up = artifact.model.predict_proba(...)[0][1]`.
- Escenarios con `_scenarios(probability_up, horizon)` (reutilizar de baseline.py).
- `dominant_features`: importancias globales del modelo × (current − midpoint global).
  Guardar midpoint/importancias en el artifact en train para no recomputar.
- `confidence` con `_confidence(prob, global_f1, global_brier)` (reutilizar).
- Warnings: si `global_f1 < 0.52` o `global_brier > 0.25`, avisar igual que hoy.

### Paso 5 · Cachear en `MarketBotService`
- `self._pooled_cache: dict[Horizon, PooledArtifact]` o un `TTLCache` (TTL ~6-24h;
  los datos diarios no cambian intra-día).
- Método `get_pooled_artifact(horizon)`: si no está o expiró, entrenar (lock para
  evitar doble-entrenamiento concurrente desde el ThreadPool del ranking).
- En `analyze_ticker`: si hay artifact → `predict_pooled`; si no (o excepción) →
  fallback a `generate_probabilistic_signal` (per-ticker actual). Loggear cuál se usó.

### Paso 6 · Warmup (app.py `_warm_rankings_cache`)
- Al inicio del loop de warmup, **entrenar el pooled para SHORT y LONG** (1 vez,
  ~unos segundos con todo el universo). Después el ranking de 60 tickers es 60
  inferencias en ms en vez de 60 entrenamientos. Ahí mueren los 65s.

### Paso 7 · Tests (`test_pooled_model.py`, offline)
- `build_pooled_dataset` con un FakeAdapter que devuelve frames sintéticos para
  3-4 tickers → X,y con la forma esperada, target alineado a H.
- `train_pooled_model` determinista (random_state) → artifact con feature_columns
  y validation poblada.
- `predict_pooled` → probability_up en [0,1], escenarios suman ~1.
- Split temporal: assert que ninguna fecha de test < máxima fecha de train.
- **NO tocar `test_validation_brier`** (sigue per-ticker).

## Verificación en vivo (OBLIGATORIA — lección de 9.1)
Los tests mockean; un bug en el path real pasa los tests pero cae al fallback.
Después de implementar:
1. Restart server, esperar warmup ("pooled train done" en log).
2. `POST /analyze` sobre NVDA/MELI/AAPL → confirmar `split=pooled_...` (NO fallback,
   NO el per-ticker viejo) y F1 global razonable (>0.52).
3. Medir `/rankings?horizon=short` cold → debería bajar de ~65s a **pocos segundos**
   (el grueso ahora es el fetch de yfinance batch, no el ML).
4. `python3 -m pytest tests/` → mantener verde (≥92 + los nuevos de pooled).

## Riesgos / cuidados
- **Leakage temporal**: el split DEBE ser por fecha, no por row. Es el error #1 fácil.
- **Concurrencia**: el ranking entra por ThreadPool; el entrenamiento del artifact
  debe estar tras un lock (entrenar 1 vez, no 60).
- **`_build_feature_frame` compartido**: hoy vive en baseline.py. Moverlo a
  `models/features.py` o exportarlo; no duplicar la lógica.
- **Fallback siempre disponible**: si el pooled falla, el per-ticker actual sigue
  dando respuesta. No romper esa red.
- **Determinismo en tests**: `random_state=42`, sin dependencia de red.

## Definition of Done
- `/analyze` usa el pooled (split=pooled_...), no fallback, F1 global >0.52.
- `/rankings` cold baja de ~65s a pocos segundos.
- ≥92 tests + nuevos de pooled, verde.
- `/validation` sigue funcionando per-ticker (track record honesto intacto).
- Verificación en vivo hecha y anotada.
