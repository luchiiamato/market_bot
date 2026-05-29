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
