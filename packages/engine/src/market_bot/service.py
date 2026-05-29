from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime

from .config import CEDEAR_UNIVERSE, DEFAULT_UNIVERSE, SUGGESTION_UNIVERSE, is_cedear_ticker
from .contracts import (
    Catalyst,
    CatalystStatus,
    Horizon,
    RUMOR_MAX_SCENARIO_DELTA,
    ScenarioProbability,
    TickerAnalysis,
)
from .backtesting import run_long_only_backtest
from .data import InstrumentContext, MarketDataAdapter, MarketDataError, YFinanceMarketDataAdapter
from .indicators import build_indicator_snapshot, compute_indicators
from .models import (
    PooledArtifact,
    generate_probabilistic_signal,
    predict_pooled,
    target_horizon_bars,
    train_pooled_model,
)
from .signals import generate_deterministic_signal
from .strategies import (
    ProfileFilter,
    adjust_rank_for_catalysts,
    adjust_rank_for_profile,
    compute_why_for_you,
    is_index_bias_ticker,
    is_opportunity_candidate,
    passes_profile_filter,
    rank_score,
    suggest_actions,
)
from .utils import TTLCache
from .validation import (
    BrierResult,
    ReliabilityBin,
    brier_score,
    reliability_bins,
    walk_forward_predictions,
)


class MarketBotService:
    def __init__(self, adapter: MarketDataAdapter | None = None):
        self.adapter = adapter or YFinanceMarketDataAdapter()
        self._analysis_cache: TTLCache[TickerAnalysis] = TTLCache(ttl_seconds=900)
        self._rankings_cache: TTLCache[list[tuple[TickerAnalysis, float, list[str]]]] = TTLCache(
            ttl_seconds=600
        )
        # Sprint 9.2: pooled model artifact per horizon (trained once, reused for
        # all tickers → ms inference instead of per-ticker RF training). 6h TTL.
        # A lock so the ranking ThreadPool can't trigger N concurrent trainings.
        import threading

        self._pooled_cache: TTLCache[PooledArtifact] = TTLCache(ttl_seconds=21_600)
        self._pooled_lock = threading.Lock()

    def _get_cached_pooled(self, horizon: Horizon) -> PooledArtifact | None:
        """Non-blocking read of the pooled artifact. analyze_ticker uses this so
        a request NEVER blocks on training; the warmup trains it in background."""
        return self._pooled_cache.get(horizon.value)

    def ensure_pooled_artifact(
        self, horizon: Horizon, universe: list[str] | None = None
    ) -> PooledArtifact | None:
        """Train + cache the pooled artifact if missing. Called by the warmup.
        Behind a lock so concurrent callers don't all train. Soft-fails to None."""
        cached = self._pooled_cache.get(horizon.value)
        if cached is not None:
            return cached
        with self._pooled_lock:
            cached = self._pooled_cache.get(horizon.value)
            if cached is not None:
                return cached
            uni = universe or SUGGESTION_UNIVERSE
            try:
                artifact = train_pooled_model(self.adapter, uni, horizon)
            except Exception:
                return None
            return self._pooled_cache.set(horizon.value, artifact)

    # Quality gate — gate on ACCURACY, not F1. Live verification (2026-05-30,
    # Sprint 9.2b) showed F1 is gameable by class imbalance: the pooled LONG model
    # scored F1=0.634 but accuracy=0.503 (chance) — a degenerate "always predict
    # up" that F1 rewards because markets drift up. Accuracy vs ~0.5 base rate is
    # the honest bar. The pooled model currently sits at chance (acc ~0.50-0.51 on
    # both horizons) → it stays GATED OFF and the per-ticker model remains primary.
    # If a future pooled model genuinely beats chance, this gate activates it
    # automatically (and unlocks the ranking speed win). See docs/sprint-9.2-pooled-model.md.
    MIN_POOLED_ACCURACY = 0.53

    def _probabilistic_for(self, enriched_history, indicators, deterministic, horizon):
        """Return (signal, validation). Uses the pooled model ONLY when its
        artifact is cached AND its holdout accuracy ≥ MIN_POOLED_ACCURACY;
        otherwise the per-ticker model. Never blocks on training, never raises."""
        artifact = self._get_cached_pooled(horizon)
        if artifact is not None and getattr(artifact.validation, "accuracy", 0.0) >= self.MIN_POOLED_ACCURACY:
            try:
                signal = predict_pooled(artifact, enriched_history, horizon)
                return signal, artifact.validation
            except Exception:
                pass
        out = generate_probabilistic_signal(enriched_history, indicators, deterministic, horizon)
        return out.signal, out.validation

    def analyze_ticker(
        self,
        ticker: str,
        horizon: Horizon,
        include_context: bool = True,
        include_backtest: bool = True,
    ) -> TickerAnalysis:
        normalized_ticker = ticker.upper()
        cache_key = (normalized_ticker, horizon.value, include_context, include_backtest)
        cached = self._analysis_cache.get(cache_key)
        if cached is not None:
            return cached

        price_history = self.adapter.get_price_history(normalized_ticker, horizon)
        enriched_history = compute_indicators(price_history.frame)
        indicators = build_indicator_snapshot(enriched_history)
        deterministic = generate_deterministic_signal(enriched_history, horizon)
        probabilistic_raw, probabilistic_validation = self._probabilistic_for(
            enriched_history, indicators, deterministic, horizon
        )
        backtest = run_long_only_backtest(price_history.frame, horizon) if include_backtest else None
        if include_context:
            context = self.adapter.get_instrument_context(normalized_ticker)
            catalysts, guardrails = _build_contextual_notes(context, indicators)
        else:
            catalysts, guardrails = [], []

        probabilistic_signal = _apply_rumor_policy(probabilistic_raw, catalysts)
        actions = suggest_actions(horizon, deterministic, probabilistic_signal)

        analysis = TickerAnalysis(
            ticker=normalized_ticker,
            horizon=horizon,
            generated_at=datetime.utcnow(),
            indicators=indicators,
            deterministic=deterministic,
            probabilistic=probabilistic_signal,
            validation=probabilistic_validation,
            backtest=backtest,
            actions=actions,
            catalysts=catalysts,
            guardrails=guardrails,
        )
        return self._analysis_cache.set(cache_key, analysis)

    def rank_universe(
        self,
        horizon: Horizon,
        tickers: list[str] | None = None,
        limit: int = 10,
        cedear_only: bool = True,
        profile: ProfileFilter | None = None,
        mode: str = "default",
    ) -> list[tuple[TickerAnalysis, float, list[str]]]:
        """Rank the universe with profile-aware filtering + catalyst-aware boosts.

        ``mode`` controls how aggressively we surface "moving" names:

        - ``"default"``: apply catalyst boost on top of the base score so SNOW-on-earnings
          climbs above static mega-caps, but everything still appears.
        - ``"opportunities"``: hard filter — only tickers with a live catalyst, a volume
          spike, or outsized volatility survive. Index ETFs (SPY/QQQ/IBB) are dropped.
          This is the mode for "find me something interesting today".
        """
        normalized_mode = mode if mode in {"default", "opportunities"} else "default"

        # Cache key includes profile so the same user gets a stable ranking.
        profile_key = (
            (profile.investor_profile, profile.risk_tolerance, profile.preferred_horizon, profile.preferred_instrument_types)
            if profile
            else None
        )
        cache_key = (
            horizon.value,
            tuple(tickers) if tickers else None,
            limit,
            cedear_only,
            profile_key,
            normalized_mode,
        )
        cached = self._rankings_cache.get(cache_key)
        if cached is not None:
            return cached

        ranking: list[tuple[TickerAnalysis, float, list[str]]] = []
        default_universe = SUGGESTION_UNIVERSE if cedear_only else DEFAULT_UNIVERSE
        universe = [ticker.upper() for ticker in (tickers or default_universe)]
        if cedear_only:
            universe = [ticker for ticker in universe if is_cedear_ticker(ticker)]
        # Profile-driven instrument filter (e.g. cedear-only users skip pure stocks).
        if profile and profile.preferred_instrument_types == "cedear":
            universe = [ticker for ticker in universe if is_cedear_ticker(ticker)]
        # In opportunities mode, drop the broad index ETFs up-front — the user
        # is asking for movers, not market beta.
        if normalized_mode == "opportunities":
            universe = [t for t in universe if not is_index_bias_ticker(t)]

        if not universe:
            return self._rankings_cache.set(cache_key, [])

        # Warm the adapter's price cache with a single batched yfinance call
        # so each thread-pool worker hits a cache instead of issuing its own
        # HTTP request. Best-effort: if the adapter doesn't expose the
        # method (custom adapter / test stub) or the batch fails, the per-
        # ticker path still works — it's just slower.
        prefetch = getattr(self.adapter, "prefetch_universe", None)
        if callable(prefetch):
            try:
                prefetch(universe, horizon)
            except Exception:
                pass

        max_workers = min(6, len(universe))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(self._analyze_for_ranking, ticker, horizon): ticker
                for ticker in universe
            }
            for future in as_completed(future_map):
                analysis = future.result()
                if analysis is None:
                    continue
                if profile and not passes_profile_filter(analysis, profile):
                    continue
                if normalized_mode == "opportunities" and not is_opportunity_candidate(analysis):
                    continue
                base = rank_score(analysis.deterministic, analysis.probabilistic)
                profile_adjusted = (
                    adjust_rank_for_profile(base, analysis, profile) if profile else base
                )
                catalyst_adjusted, catalyst_reasons = adjust_rank_for_catalysts(
                    profile_adjusted, analysis
                )
                profile_reasons = compute_why_for_you(analysis, profile) if profile else []
                # Catalyst reasons go first so the user sees *why this jumped* before
                # the profile rationalisation.
                reasons = catalyst_reasons + profile_reasons
                ranking.append((analysis, catalyst_adjusted, reasons[:4]))

        ranking.sort(key=lambda item: item[1], reverse=True)
        return self._rankings_cache.set(cache_key, ranking[:limit])

    def suggested_cedear_universe(self) -> list[str]:
        return CEDEAR_UNIVERSE.copy()

    def validate_ticker(
        self,
        ticker: str,
        horizon: Horizon,
        *,
        warmup: int = 60,
        horizon_days: int | None = None,
        step_days: int = 5,
    ) -> BrierResult:
        """Run walk-forward calibration for ``ticker`` and return Brier metrics.

        ``step_days`` defaults to 5 so a 1-year history produces ~50 anchors —
        enough for a stable estimate without forcing the engine to recompute
        the probabilistic signal on every single day.

        Sprint 9.1: ``horizon_days`` defaults to the SAME horizon the model
        predicts (``target_horizon_bars``), so the Brier "track record" measures
        the model against the exact target it was trained on — not next-bar.
        Callers can still override explicitly.
        """
        if horizon_days is None:
            horizon_days = target_horizon_bars(horizon)
        normalized_ticker = ticker.upper()
        price_history = self.adapter.get_price_history(normalized_ticker, horizon)
        enriched_history = compute_indicators(price_history.frame)

        def predictor(frame_slice):
            indicators = build_indicator_snapshot(frame_slice)
            deterministic = generate_deterministic_signal(frame_slice, horizon)
            probabilistic = generate_probabilistic_signal(
                frame_slice, indicators, deterministic, horizon
            )
            return float(probabilistic.signal.probability_up)

        predictions, labels = walk_forward_predictions(
            enriched_history,
            predictor,
            warmup=warmup,
            horizon_days=horizon_days,
            step_days=step_days,
        )
        return BrierResult(
            sample_size=len(predictions),
            brier_score=brier_score(predictions, labels),
            reliability_bins=reliability_bins(predictions, labels),
        )

    def _analyze_for_ranking(self, ticker: str, horizon: Horizon) -> TickerAnalysis | None:
        try:
            return self.analyze_ticker(
                ticker,
                horizon,
                include_context=False,
                include_backtest=False,
            )
        except Exception:
            return None


def _build_contextual_notes(
    context: InstrumentContext,
    indicators,
) -> tuple[list[Catalyst], list[str]]:
    catalysts: list[Catalyst] = []
    guardrails: list[str] = []
    now = datetime.utcnow()

    if context.sector:
        catalysts.append(
            Catalyst(
                name=f"Sector: {context.sector}",
                category="context",
                impact="medium",
                status=CatalystStatus.INFERRED,
                observed_at=now,
            )
        )

    if context.earnings_date:
        catalysts.append(
            Catalyst(
                name=f"Proximo evento reportado: {context.earnings_date}",
                category="earnings",
                impact="high",
                status=CatalystStatus.CONFIRMED,
                observed_at=now,
            )
        )
        earnings_guardrail = _earnings_guardrail(context.earnings_date)
        if earnings_guardrail:
            guardrails.append(earnings_guardrail)

    # Promote credible recent news into catalysts. We import lazily so the
    # engine still works in environments where the reference_data package
    # is unavailable (e.g. unit tests with a stubbed adapter).
    try:
        from market_reference.news import recent_high_confidence_items  # type: ignore

        for news in recent_high_confidence_items(context.ticker, max_age_hours=48, min_confidence=0.6):
            catalysts.append(
                Catalyst(
                    name=news.title[:140],
                    category=news.impact_category,
                    impact="high" if abs(news.sentiment) >= 0.3 else "medium",
                    status=CatalystStatus.REPORTED,
                    source_url=news.url,
                    observed_at=_parse_iso(news.published_at) or _parse_iso(news.fetched_at) or now,
                )
            )
    except Exception:
        # News pipeline failures should never break /analyze.
        pass

    if indicators.atr and indicators.price and (indicators.atr / indicators.price) > 0.04:
        guardrails.append("La volatilidad del activo es alta. Reducir tamano y evitar perseguir precio.")

    if indicators.volume_ratio and indicators.volume_ratio < 0.8:
        guardrails.append("El volumen reciente es flojo. Exigir confirmacion adicional antes de entrar.")

    if indicators.adx and indicators.adx < 18:
        guardrails.append("La tendencia esta debil. Un mercado lateral degrada setups direccionales.")

    if not guardrails:
        guardrails.append("No se detectaron bloqueos mayores, pero la tesis debe revisarse contra el mercado general.")

    return catalysts, guardrails


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, AttributeError):
        return None


def _earnings_guardrail(raw_date: str) -> str | None:
    try:
        earnings_date = date.fromisoformat(raw_date[:10])
    except ValueError:
        return None
    days_until = (earnings_date - date.today()).days
    if 0 <= days_until <= 14:
        return "Hay un evento de earnings cercano. El gap risk puede invalidar setups tecnicos limpios."
    return None


def _apply_rumor_policy(signal, catalysts: list[Catalyst]):
    """Enforce the rumor-weight policy on a probabilistic signal.

    Rumored catalysts are allowed to nudge scenario probabilities by no more
    than :data:`RUMOR_MAX_SCENARIO_DELTA` in absolute terms. A rumor cannot,
    on its own, flip the dominant direction — that requires at least one
    ``reported`` or ``confirmed`` catalyst pointing the same way.

    The signal is returned unchanged when no rumored catalysts are present.
    """
    rumored = [c for c in catalysts if c.status == CatalystStatus.RUMORED]
    if not rumored or not signal.scenarios:
        return signal

    has_credible_support = any(
        c.status in (CatalystStatus.CONFIRMED, CatalystStatus.REPORTED)
        for c in catalysts
    )

    capped_scenarios: list[ScenarioProbability] = []
    for scenario in signal.scenarios:
        if has_credible_support:
            capped_scenarios.append(scenario)
            continue
        # No credible backing — cap deviation from a neutral baseline (1/N).
        baseline = 1.0 / len(signal.scenarios)
        delta = scenario.probability - baseline
        if abs(delta) > RUMOR_MAX_SCENARIO_DELTA:
            adjusted = baseline + (RUMOR_MAX_SCENARIO_DELTA if delta > 0 else -RUMOR_MAX_SCENARIO_DELTA)
            capped_scenarios.append(
                ScenarioProbability(
                    label=scenario.label,
                    probability=round(adjusted, 4),
                    thesis=scenario.thesis,
                )
            )
        else:
            capped_scenarios.append(scenario)

    warnings = list(signal.warnings)
    if not has_credible_support:
        warnings.append(
            "Catalysts dominados por rumores: escenarios capeados por rumor-policy."
        )

    # Re-normalise so probabilities sum to 1.0 (within float tolerance).
    total = sum(s.probability for s in capped_scenarios)
    if total > 0:
        capped_scenarios = [
            ScenarioProbability(
                label=s.label,
                probability=round(s.probability / total, 4),
                thesis=s.thesis,
            )
            for s in capped_scenarios
        ]

    return type(signal)(
        confidence=signal.confidence,
        probability_up=_probability_up_from_scenarios(capped_scenarios, signal.probability_up),
        scenarios=capped_scenarios,
        dominant_features=signal.dominant_features,
        warnings=warnings,
    )


def _probability_up_from_scenarios(
    scenarios: list[ScenarioProbability], fallback: float
) -> float:
    if not scenarios:
        return fallback

    probability_up = 0.0
    saw_directional_label = False
    for scenario in scenarios:
        label = scenario.label.lower()
        if label == "bull":
            probability_up += scenario.probability
            saw_directional_label = True
        elif label in {"base", "neutral"}:
            probability_up += scenario.probability * 0.5
            saw_directional_label = True

    if not saw_directional_label:
        return fallback
    return round(max(0.0, min(1.0, probability_up)), 2)
