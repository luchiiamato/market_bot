from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime

from .config import CEDEAR_UNIVERSE, DEFAULT_UNIVERSE, SUGGESTION_UNIVERSE, is_cedear_ticker
from .contracts import Catalyst, Horizon, TickerAnalysis
from .backtesting import run_long_only_backtest
from .data import InstrumentContext, MarketDataAdapter, MarketDataError, YFinanceMarketDataAdapter
from .indicators import build_indicator_snapshot, compute_indicators
from .models import generate_probabilistic_signal
from .signals import generate_deterministic_signal
from .strategies import rank_score, suggest_actions
from .utils import TTLCache


class MarketBotService:
    def __init__(self, adapter: MarketDataAdapter | None = None):
        self.adapter = adapter or YFinanceMarketDataAdapter()
        self._analysis_cache: TTLCache[TickerAnalysis] = TTLCache(ttl_seconds=180)
        self._rankings_cache: TTLCache[list[tuple[TickerAnalysis, float]]] = TTLCache(ttl_seconds=600)

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
        context = (
            self.adapter.get_instrument_context(normalized_ticker)
            if include_context
            else InstrumentContext(ticker=normalized_ticker, display_name=normalized_ticker)
        )
        enriched_history = compute_indicators(price_history.frame)
        indicators = build_indicator_snapshot(enriched_history)
        deterministic = generate_deterministic_signal(enriched_history, horizon)
        probabilistic_output = generate_probabilistic_signal(
            enriched_history, indicators, deterministic, horizon
        )
        backtest = run_long_only_backtest(price_history.frame, horizon) if include_backtest else None
        actions = suggest_actions(horizon, deterministic, probabilistic_output.signal)
        catalysts, guardrails = _build_contextual_notes(context, indicators)

        analysis = TickerAnalysis(
            ticker=normalized_ticker,
            horizon=horizon,
            generated_at=datetime.utcnow(),
            indicators=indicators,
            deterministic=deterministic,
            probabilistic=probabilistic_output.signal,
            validation=probabilistic_output.validation,
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
    ) -> list[tuple[TickerAnalysis, float]]:
        cache_key = (
            horizon.value,
            tuple(tickers) if tickers else None,
            limit,
            cedear_only,
        )
        cached = self._rankings_cache.get(cache_key)
        if cached is not None:
            return cached

        ranking: list[tuple[TickerAnalysis, float]] = []
        default_universe = SUGGESTION_UNIVERSE if cedear_only else DEFAULT_UNIVERSE
        universe = [ticker.upper() for ticker in (tickers or default_universe)]
        if cedear_only:
            universe = [ticker for ticker in universe if is_cedear_ticker(ticker)]
        if not universe:
            return self._rankings_cache.set(cache_key, [])

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
                ranking.append((analysis, rank_score(analysis.deterministic, analysis.probabilistic)))

        ranking.sort(key=lambda item: item[1], reverse=True)
        return self._rankings_cache.set(cache_key, ranking[:limit])

    def suggested_cedear_universe(self) -> list[str]:
        return CEDEAR_UNIVERSE.copy()

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

    if context.sector:
        catalysts.append(
            Catalyst(
                name=f"Sector: {context.sector}",
                category="context",
                impact="medium",
            )
        )

    if context.earnings_date:
        catalysts.append(
            Catalyst(
                name=f"Proximo evento reportado: {context.earnings_date}",
                category="earnings",
                impact="high",
            )
        )
        earnings_guardrail = _earnings_guardrail(context.earnings_date)
        if earnings_guardrail:
            guardrails.append(earnings_guardrail)

    if indicators.atr and indicators.price and (indicators.atr / indicators.price) > 0.04:
        guardrails.append("La volatilidad del activo es alta. Reducir tamano y evitar perseguir precio.")

    if indicators.volume_ratio and indicators.volume_ratio < 0.8:
        guardrails.append("El volumen reciente es flojo. Exigir confirmacion adicional antes de entrar.")

    if indicators.adx and indicators.adx < 18:
        guardrails.append("La tendencia esta debil. Un mercado lateral degrada setups direccionales.")

    if not guardrails:
        guardrails.append("No se detectaron bloqueos mayores, pero la tesis debe revisarse contra el mercado general.")

    return catalysts, guardrails


def _earnings_guardrail(raw_date: str) -> str | None:
    try:
        earnings_date = date.fromisoformat(raw_date[:10])
    except ValueError:
        return None
    days_until = (earnings_date - date.today()).days
    if 0 <= days_until <= 14:
        return "Hay un evento de earnings cercano. El gap risk puede invalidar setups tecnicos limpios."
    return None
