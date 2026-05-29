from __future__ import annotations

import logging
import time
from dataclasses import asdict
from datetime import date, datetime

import pandas as pd

from market_bot.utils import TTLCache
from market_identity.store import connection
from market_reference import ArgentinaBenchmarkError, ArgentinaBenchmarkService
from market_reference.classification import aggregate_exposure

from .cedears import (
    CedearReference,
    build_byma_symbol,
    normalize_cedear_symbol,
    normalize_quote_symbol,
    resolve_cedear_reference,
    to_market_data_symbol,
)
from .models import (
    BenchmarkComparison,
    ExposureBucket,
    PortfolioSummary,
    PositionRecord,
    PositionValuation,
)

logger = logging.getLogger("market_bot.api")


class PortfolioError(RuntimeError):
    """Raised when portfolio operations cannot be completed."""


class PortfolioService:
    def __init__(self, benchmark_service: ArgentinaBenchmarkService | None = None) -> None:
        self.benchmark_service = benchmark_service or ArgentinaBenchmarkService()
        # 15-min TTL: yfinance daily closes are EOD, so caching ~quarter-hour
        # is safe and cuts repeat /portfolio/summary calls to a no-op.
        self._quote_cache: TTLCache[tuple[float, date]] = TTLCache(ttl_seconds=900)
        # Previous-day close stored alongside the current quote so we can
        # compute intra-day change % without an extra network round-trip.
        self._prev_close_cache: TTLCache[float] = TTLCache(ttl_seconds=900)
        self._ensure_schema()

    def add_position(
        self,
        user_id: int,
        instrument_type: str,
        symbol: str,
        quantity: float,
        purchase_date: date,
        purchase_price: float,
        purchase_currency: str,
        benchmark_preference: str,
        risk_tolerance: str = "medium",
        underlying_ticker: str | None = None,
        cedear_ratio: float | None = None,
        notes: str = "",
        purchase_ccl: float | None = None,
        purchase_mep: float | None = None,
        purchase_official: float | None = None,
    ) -> PositionValuation:
        prepared = self._prepare_position_payload(
            instrument_type=instrument_type,
            symbol=symbol,
            quantity=quantity,
            purchase_price=purchase_price,
            purchase_currency=purchase_currency,
            underlying_ticker=underlying_ticker,
            cedear_ratio=cedear_ratio,
            notes=notes,
        )

        now = datetime.utcnow().isoformat()
        with connection() as conn:
            conn.execute(
                """
                INSERT INTO positions (
                    user_id,
                    instrument_type,
                    symbol,
                    underlying_ticker,
                    byma_symbol,
                    cedear_ratio,
                    cedear_ratio_source,
                    quantity,
                    purchase_date,
                    purchase_price,
                    purchase_currency,
                    notes,
                    created_at,
                    updated_at,
                    purchase_ccl,
                    purchase_mep,
                    purchase_official
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    prepared["instrument_type"],
                    prepared["symbol"],
                    prepared["underlying_ticker"],
                    prepared["byma_symbol"],
                    prepared["cedear_ratio"],
                    prepared["cedear_ratio_source"],
                    quantity,
                    purchase_date.isoformat(),
                    purchase_price,
                    prepared["purchase_currency"],
                    prepared["notes"],
                    now,
                    now,
                    purchase_ccl,
                    purchase_mep,
                    purchase_official,
                ),
            )
            position_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

        return self.get_position_valuation(
            position_id,
            user_id,
            benchmark_preference,
            risk_tolerance=risk_tolerance,
        )

    def update_position(
        self,
        position_id: int,
        user_id: int,
        instrument_type: str,
        symbol: str,
        quantity: float,
        purchase_date: date,
        purchase_price: float,
        purchase_currency: str,
        benchmark_preference: str,
        risk_tolerance: str = "medium",
        underlying_ticker: str | None = None,
        cedear_ratio: float | None = None,
        notes: str = "",
    ) -> PositionValuation:
        prepared = self._prepare_position_payload(
            instrument_type=instrument_type,
            symbol=symbol,
            quantity=quantity,
            purchase_price=purchase_price,
            purchase_currency=purchase_currency,
            underlying_ticker=underlying_ticker,
            cedear_ratio=cedear_ratio,
            notes=notes,
        )

        now = datetime.utcnow().isoformat()
        with connection() as conn:
            existing = conn.execute(
                "SELECT id FROM positions WHERE id = ? AND user_id = ?",
                (position_id, user_id),
            ).fetchone()
            if existing is None:
                raise PortfolioError("Posicion no encontrada.")
            conn.execute(
                """
                UPDATE positions
                SET instrument_type = ?,
                    symbol = ?,
                    underlying_ticker = ?,
                    byma_symbol = ?,
                    cedear_ratio = ?,
                    cedear_ratio_source = ?,
                    quantity = ?,
                    purchase_date = ?,
                    purchase_price = ?,
                    purchase_currency = ?,
                    notes = ?,
                    updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (
                    prepared["instrument_type"],
                    prepared["symbol"],
                    prepared["underlying_ticker"],
                    prepared["byma_symbol"],
                    prepared["cedear_ratio"],
                    prepared["cedear_ratio_source"],
                    quantity,
                    purchase_date.isoformat(),
                    purchase_price,
                    prepared["purchase_currency"],
                    prepared["notes"],
                    now,
                    position_id,
                    user_id,
                ),
            )

        return self.get_position_valuation(
            position_id,
            user_id,
            benchmark_preference,
            risk_tolerance=risk_tolerance,
        )

    def list_positions(
        self,
        user_id: int,
        benchmark_preference: str,
        risk_tolerance: str = "medium",
    ) -> list[PositionValuation]:
        with connection() as conn:
            rows = conn.execute(
                "SELECT * FROM positions WHERE user_id = ? ORDER BY purchase_date DESC, id DESC",
                (user_id,),
            ).fetchall()
        records = [_record_from_row(row) for row in rows]

        # Single batched yfinance call warms the cache so each
        # _build_position_valuation -> _latest_close becomes a cache hit.
        # Wrapped in try/except: tests monkeypatch _latest_close and run
        # offline, where the batch request would fail. A failure here
        # must not break valuation — _latest_close will fall through to
        # its own (mocked in tests) fetch.
        try:
            symbols_to_prefetch: list[str] = []
            for record in records:
                if record.instrument_type == "cedear":
                    local_symbol = record.byma_symbol or build_byma_symbol(record.symbol)
                    symbols_to_prefetch.append(local_symbol)
                symbols_to_prefetch.append(record.underlying_ticker)
                symbols_to_prefetch.append(record.symbol)
            unique_symbols = list({normalize_quote_symbol(s) for s in symbols_to_prefetch if s})
            if unique_symbols:
                self.prefetch_quotes(unique_symbols)
        except Exception:
            # Prefetch is a pure optimisation — never let it block valuation.
            pass

        # Fetch current exchange rates once for the whole list — all positions
        # share the same "today" snapshot. _build_position_valuation still calls
        # build_period_snapshot per position for the purchase-date rates (which
        # vary per position), but the current_exchange leg is the same for all.
        try:
            current_exchange = self.benchmark_service.get_current_exchange_rates()
        except Exception:
            current_exchange = None

        return [
            self._build_position_valuation(
                record,
                benchmark_preference,
                risk_tolerance=risk_tolerance,
                current_exchange=current_exchange,
            )
            for record in records
        ]

    def prefetch_quotes(self, symbols: list[str]) -> None:
        """Warm ``self._quote_cache`` with one batched yfinance call.

        yfinance's ``download`` accepts a list of tickers and parallelises
        internally. With multi-ticker downloads the column index becomes a
        MultiIndex of ``(field, ticker)``; with a single ticker it stays
        flat. Both shapes are handled below.

        Missing tickers in the batch response are simply skipped — the
        caller's ``_latest_close`` will fall back to a per-symbol fetch.
        """
        normalized = sorted({normalize_quote_symbol(s) for s in symbols if s and s.strip()})
        # Skip symbols already cached (and still fresh).
        targets = [s for s in normalized if self._quote_cache.get(s) is None]
        if not targets:
            return

        try:
            import yfinance as yf  # type: ignore
        except ModuleNotFoundError:
            return

        started = time.perf_counter()
        try:
            request_symbols = [to_market_data_symbol(symbol) for symbol in targets]
            frame = yf.download(
                request_symbols,
                period="10d",
                interval="1d",
                auto_adjust=True,
                group_by="ticker",
                progress=False,
                threads=True,
            )
        except Exception:
            # Network / yfinance failures fall through to per-symbol fetch.
            return

        hits = 0
        if frame is None or getattr(frame, "empty", True):
            self._log_batch_metrics(len(targets), 0, started)
            return

        # Single-ticker response: flat columns. Multi-ticker: MultiIndex.
        if isinstance(frame.columns, pd.MultiIndex):
            available = set(frame.columns.get_level_values(0))
            for symbol in targets:
                request_symbol = to_market_data_symbol(symbol)
                if request_symbol not in available:
                    continue
                try:
                    sub = frame[request_symbol]
                except KeyError:
                    continue
                quote = _extract_latest_close(sub, symbol)
                if quote is not None:
                    self._quote_cache.set(symbol, quote)
                    hits += 1
        else:
            # Flat columns => single ticker. Only one symbol in targets.
            if len(targets) == 1:
                quote = _extract_latest_close(frame, targets[0])
                if quote is not None:
                    self._quote_cache.set(targets[0], quote)
                    hits += 1

        self._log_batch_metrics(len(targets), hits, started)

    def _log_batch_metrics(self, total: int, hits: int, started: float) -> None:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        try:
            logger.info(
                "yfinance batch fetch",
                extra={
                    "symbols": total,
                    "elapsed_ms": elapsed_ms,
                    "hit_rate": round(hits / total, 3) if total else 0.0,
                },
            )
        except Exception:
            pass

    def get_position_valuation(
        self,
        position_id: int,
        user_id: int,
        benchmark_preference: str,
        risk_tolerance: str = "medium",
    ) -> PositionValuation:
        with connection() as conn:
            row = conn.execute(
                "SELECT * FROM positions WHERE id = ? AND user_id = ?",
                (position_id, user_id),
            ).fetchone()
        if row is None:
            raise PortfolioError("Posicion no encontrada.")
        return self._build_position_valuation(
            _record_from_row(row),
            benchmark_preference,
            risk_tolerance=risk_tolerance,
        )

    def delete_position(self, position_id: int, user_id: int) -> None:
        with connection() as conn:
            conn.execute(
                "DELETE FROM positions WHERE id = ? AND user_id = ?",
                (position_id, user_id),
            )

    def clear_positions(self, user_id: int) -> None:
        with connection() as conn:
            conn.execute("DELETE FROM positions WHERE user_id = ?", (user_id,))

    def portfolio_summary(
        self,
        user_id: int,
        benchmark_preference: str,
        risk_tolerance: str = "medium",
    ) -> PortfolioSummary:
        positions = self.list_positions(
            user_id,
            benchmark_preference,
            risk_tolerance=risk_tolerance,
        )
        total_value_ars = sum(item.current_value_ars for item in positions)
        total_value_usd = sum(item.current_value_usd for item in positions)
        total_cost_ars = sum(item.cost_basis_ars for item in positions)
        total_cost_usd = sum(item.cost_basis_usd for item in positions)
        total_pnl_ars = total_value_ars - total_cost_ars
        total_pnl_usd = total_value_usd - total_cost_usd

        preferred_label = PREFERENCE_TO_COMPARISON_LABEL.get(
            benchmark_preference.strip().lower(), "inflation"
        )

        # Concentration buckets — used by the portfolio summary UI to surface
        # "where am I really invested?". Built off the live valuations so the
        # weights reflect current market value, not cost basis.
        sector_exposure = [
            ExposureBucket(**item) for item in aggregate_exposure(positions, "sector")
        ]
        region_exposure = [
            ExposureBucket(**item) for item in aggregate_exposure(positions, "region")
        ]

        return PortfolioSummary(
            positions_count=len(positions),
            total_value_ars=round(total_value_ars, 2),
            total_value_usd=round(total_value_usd, 2),
            total_cost_ars=round(total_cost_ars, 2),
            total_cost_usd=round(total_cost_usd, 2),
            total_pnl_ars=round(total_pnl_ars, 2),
            total_pnl_usd=round(total_pnl_usd, 2),
            total_return_pct_ars=round(_safe_return(total_value_ars, total_cost_ars), 4),
            total_return_pct_usd=round(_safe_return(total_value_usd, total_cost_usd), 4),
            total_real_return_pct=round(_aggregate_real_return(positions), 4),
            total_preferred_benchmark_return_pct=round(
                _aggregate_preferred_benchmark_return(positions, benchmark_preference), 4
            ),
            preferred_benchmark_label=preferred_label,
            positions=positions,
            sector_exposure=sector_exposure,
            region_exposure=region_exposure,
        )

    def custom_benchmark_comparison(
        self,
        user_id: int,
        ticker: str,
        benchmark_preference: str,
        risk_tolerance: str = "medium",
    ) -> dict:
        """Compute "what if I had bought TICKER instead of my actual portfolio".

        For each position, take the ARS cost at purchase, convert to USD at the
        purchase-date CCL, "buy" TICKER at its closing price on that date, then
        re-value at today's price × current CCL. Sum across positions to get
        the hypothetical tracked value.

        This powers the ad-hoc benchmark feature so the user can ask
        "what would I have today if I had bought SPY / VOO / BTC-USD / GLD
        instead of these stocks?".
        """
        normalized_ticker = ticker.strip().upper()
        if not normalized_ticker:
            raise PortfolioError("Ticker requerido.")

        positions = self.list_positions(
            user_id,
            benchmark_preference,
            risk_tolerance=risk_tolerance,
        )
        if not positions:
            raise PortfolioError("Necesitás cargar posiciones para comparar contra un benchmark custom.")

        # Fetch full price history once and look up by date.
        try:
            import yfinance as yf  # type: ignore
        except ModuleNotFoundError as exc:
            raise PortfolioError("yfinance no esta instalado.") from exc

        oldest = min(p.purchase_date for p in positions)
        # Buffer the window so we can find the closest valid close even if the
        # purchase fell on a weekend / holiday.
        start = (oldest - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
        try:
            history = yf.download(
                normalized_ticker,
                start=start,
                interval="1d",
                auto_adjust=True,
                progress=False,
            )
        except Exception as exc:
            raise PortfolioError(f"No se pudo obtener historia para {normalized_ticker}.") from exc

        if history is None or history.empty:
            raise PortfolioError(f"Sin datos para {normalized_ticker}.")
        if isinstance(history.columns, pd.MultiIndex):
            try:
                close_series = history["Close"][normalized_ticker]
            except Exception:
                close_series = history["Close"].iloc[:, 0]
        else:
            close_series = history["Close"]
        close_series = close_series.dropna()
        if close_series.empty:
            raise PortfolioError(f"Serie de cierres vacía para {normalized_ticker}.")

        latest_price_usd = float(close_series.iloc[-1])
        current_ccl = self.benchmark_service.get_current_exchange_rates().ccl

        total_cost_ars = 0.0
        total_tracked_ars = 0.0
        per_position_breakdown: list[dict] = []

        for position in positions:
            cost_ars = float(position.cost_basis_ars)
            total_cost_ars += cost_ars

            # USD invested at purchase-date CCL.
            snapshot = self.benchmark_service.build_period_snapshot(
                position.purchase_date, date.today()
            )
            purchase_ccl = snapshot.purchase_exchange.ccl
            if purchase_ccl <= 0:
                continue
            usd_invested = cost_ars / purchase_ccl

            # Closing price on or before the purchase date.
            purchase_ts = pd.Timestamp(position.purchase_date)
            window = close_series.loc[:purchase_ts]
            if window.empty:
                # Ticker didn't exist yet on that date — skip but record it.
                per_position_breakdown.append({
                    "symbol": position.symbol,
                    "purchase_date": position.purchase_date.isoformat(),
                    "skipped": True,
                    "reason": "ticker no listado en esa fecha",
                })
                continue
            purchase_price_usd = float(window.iloc[-1])
            if purchase_price_usd <= 0:
                continue

            hypothetical_shares = usd_invested / purchase_price_usd
            current_value_usd = hypothetical_shares * latest_price_usd
            current_value_ars = current_value_usd * current_ccl
            total_tracked_ars += current_value_ars

            per_position_breakdown.append({
                "symbol": position.symbol,
                "purchase_date": position.purchase_date.isoformat(),
                "cost_ars": round(cost_ars, 2),
                "usd_invested": round(usd_invested, 2),
                "hypothetical_shares": round(hypothetical_shares, 6),
                "current_value_ars": round(current_value_ars, 2),
            })

        outperformance_ars = total_tracked_ars - total_cost_ars
        outperformance_pct = (
            outperformance_ars / total_cost_ars if total_cost_ars > 0 else 0.0
        )

        return {
            "ticker": normalized_ticker,
            "label": normalized_ticker,
            "tracked_value_ars": round(total_tracked_ars, 2),
            "outperformance_ars": round(outperformance_ars, 2),
            "outperformance_pct": round(outperformance_pct, 4),
            "current_price_usd": round(latest_price_usd, 4),
            "current_ccl": round(current_ccl, 2),
            "sample_size": len([b for b in per_position_breakdown if not b.get("skipped")]),
            "breakdown": per_position_breakdown,
        }

    def diagnostics(
        self,
        user_id: int,
        benchmark_preference: str,
        risk_tolerance: str = "medium",
    ) -> dict:
        """Per-position raw values used in the valuation.

        Exposed so we can debug *why* a portfolio value looks wrong. If the
        ARS total is off, this endpoint shows the local BYMA price + underlying
        USD price + ratio used for each position. The wrong one is usually
        a yfinance fetch returning stale or misaligned data for the .BA ticker.
        """
        positions = self.list_positions(
            user_id,
            benchmark_preference,
            risk_tolerance=risk_tolerance,
        )
        current_exchange = self.benchmark_service.get_current_exchange_rates()

        breakdown = []
        for p in positions:
            implied_fx = (
                p.current_value_ars / p.current_value_usd
                if p.current_value_usd
                else 0.0
            )
            breakdown.append({
                "symbol": p.symbol,
                "instrument_type": p.instrument_type,
                "quantity": p.quantity,
                "cedear_ratio": p.cedear_ratio,
                "ratio_source": p.cedear_ratio_source,
                "current_price": p.current_price,
                "current_price_currency": p.current_price_currency,
                "current_value_ars": p.current_value_ars,
                "current_value_usd": p.current_value_usd,
                "cost_basis_ars": p.cost_basis_ars,
                "cost_basis_usd": p.cost_basis_usd,
                "implied_fx": round(implied_fx, 2),
                "fx_drift_pct": (
                    round((implied_fx - current_exchange.ccl) / current_exchange.ccl * 100, 2)
                    if current_exchange.ccl
                    else 0.0
                ),
            })

        return {
            "as_of": date.today().isoformat(),
            "current_ccl": current_exchange.ccl,
            "current_mep": current_exchange.mep,
            "current_official": current_exchange.official,
            "positions": breakdown,
        }

    def _build_position_valuation(
        self,
        position: PositionRecord,
        benchmark_preference: str,
        risk_tolerance: str = "medium",
        current_exchange=None,
    ) -> PositionValuation:
        today = date.today()
        snapshot = self.benchmark_service.build_period_snapshot(position.purchase_date, today)
        selected_house = _normalize_benchmark_preference(benchmark_preference)
        # Use hoisted current_exchange when available — same rates for all positions.
        effective_current = current_exchange if current_exchange is not None else snapshot.current_exchange
        current_fx = _pick_fx(effective_current, selected_house)

        notes: list[str] = []
        if position.instrument_type == "cedear":
            local_symbol = position.byma_symbol or build_byma_symbol(position.symbol)
            local_price_ars, quote_date = self._latest_close(local_symbol)
            change_pct_1d = self._daily_change_pct(local_symbol)
            underlying_price_usd, _ = self._latest_close(position.underlying_ticker)
            current_value_ars = position.quantity * local_price_ars
            # USD value for CEDEAR uses CCL conversion of the ARS market value.
            # This is robust against ratio inference errors: even if the stored
            # cedear_ratio is wrong, the USD figure still reflects what the user
            # would get by selling the CEDEARs and dollarizing through CCL.
            # The (qty / ratio) × underlying_price formula gave wildly wrong USD
            # when the ratio fell back to 1.0 or to a parity-snapped neighbor.
            current_ccl = effective_current.ccl
            if current_ccl > 0:
                current_value_usd = current_value_ars / current_ccl
            else:
                # Last-resort fallback that at least doesn't blow up.
                cedear_ratio = position.cedear_ratio or 1.0
                current_value_usd = (position.quantity / cedear_ratio) * underlying_price_usd
            current_price = local_price_ars
            current_currency = "ARS"
            if position.cedear_ratio_source == "estimated_market_parity":
                notes.append("La relacion CEDEAR se estimo por paridad de mercado y conviene validarla.")
            if position.cedear_ratio_source == "fallback_default":
                notes.append(
                    "No se pudo inferir la relacion CEDEAR para este ticker. "
                    "El valor en USD se calcula via CCL, pero verificar la cantidad efectiva de subyacente."
                )
        else:
            underlying_price_usd, quote_date = self._latest_close(position.underlying_ticker)
            change_pct_1d = self._daily_change_pct(position.underlying_ticker)
            current_value_usd = position.quantity * underlying_price_usd
            current_value_ars = current_value_usd * current_fx
            current_price = underlying_price_usd
            current_currency = "USD"

        cost_basis_ars, cost_basis_usd = self._cost_basis(position, snapshot, selected_house)
        comparisons = self._benchmark_comparisons(cost_basis_ars, current_value_ars, snapshot)
        inflation_track = next(item.tracked_value_ars for item in comparisons if item.label == "inflation")

        # Earnings-aware guardrails. Soft-fail: if the reference_data package
        # is unavailable or yfinance is offline, skip without breaking
        # valuation.
        try:
            from market_reference.earnings import earnings_guardrail_for_holding  # type: ignore

            note = earnings_guardrail_for_holding(position.underlying_ticker, risk_tolerance)
            if note:
                notes.append(note)
        except Exception:
            pass

        # Per-position return vs the user's preferred FX benchmark (MEP/CCL/Oficial).
        # We resolve the label here so the UI can display "vs MEP +5%" or similar
        # without recomputing on every render.
        preferred_label = PREFERENCE_TO_COMPARISON_LABEL.get(
            benchmark_preference.strip().lower(), "inflation"
        )
        preferred_tracked = next(
            (cmp.tracked_value_ars for cmp in comparisons if cmp.label == preferred_label),
            inflation_track,
        )
        preferred_return = _safe_return(current_value_ars, preferred_tracked)

        return PositionValuation(
            position_id=position.position_id,
            instrument_type=position.instrument_type,
            symbol=position.symbol,
            underlying_ticker=position.underlying_ticker,
            byma_symbol=position.byma_symbol,
            cedear_ratio=position.cedear_ratio,
            cedear_ratio_source=position.cedear_ratio_source,
            quantity=position.quantity,
            purchase_date=position.purchase_date,
            purchase_price=position.purchase_price,
            purchase_currency=position.purchase_currency,
            user_notes=position.notes,
            current_price=round(current_price, 2),
            current_price_currency=current_currency,
            quote_as_of=quote_date,
            current_value_ars=round(current_value_ars, 2),
            current_value_usd=round(current_value_usd, 2),
            cost_basis_ars=round(cost_basis_ars, 2),
            cost_basis_usd=round(cost_basis_usd, 2),
            pnl_ars=round(current_value_ars - cost_basis_ars, 2),
            pnl_usd=round(current_value_usd - cost_basis_usd, 2),
            return_pct_ars=round(_safe_return(current_value_ars, cost_basis_ars), 4),
            return_pct_usd=round(_safe_return(current_value_usd, cost_basis_usd), 4),
            real_return_pct=round(_safe_return(current_value_ars, inflation_track), 4),
            preferred_benchmark_return_pct=round(preferred_return, 4),
            preferred_benchmark_label=preferred_label,
            change_pct_1d=round(change_pct_1d, 4),
            benchmark_comparisons=comparisons,
            notes=notes,
        )

    def _prepare_position_payload(
        self,
        instrument_type: str,
        symbol: str,
        quantity: float,
        purchase_price: float,
        purchase_currency: str,
        underlying_ticker: str | None = None,
        cedear_ratio: float | None = None,
        notes: str = "",
    ) -> dict:
        normalized_type = instrument_type.strip().lower()
        if normalized_type not in {"stock", "cedear"}:
            raise PortfolioError("El tipo de instrumento debe ser stock o cedear.")
        if quantity <= 0 or purchase_price <= 0:
            raise PortfolioError("Cantidad y precio de compra deben ser positivos.")

        normalized_symbol = normalize_cedear_symbol(symbol)
        normalized_currency = purchase_currency.strip().upper()
        ratio_value = None
        ratio_source = None
        byma_symbol = None
        resolved_underlying = normalize_cedear_symbol(underlying_ticker or normalized_symbol)

        if normalized_type == "cedear":
            current_ccl = self.benchmark_service.get_current_exchange_rates().ccl
            local_price, _ = self._latest_close(build_byma_symbol(normalized_symbol))
            underlying_price, _ = self._latest_close(resolved_underlying)
            reference = resolve_cedear_reference(
                symbol=normalized_symbol,
                underlying_ticker=resolved_underlying,
                user_ratio=cedear_ratio,
                current_ccl=current_ccl,
                local_price_ars=local_price,
                underlying_price_usd=underlying_price,
            )
            byma_symbol = reference.byma_symbol
            resolved_underlying = reference.underlying_ticker
            ratio_value = reference.cedear_ratio
            ratio_source = reference.ratio_source

        return {
            "instrument_type": normalized_type,
            "symbol": normalized_symbol,
            "purchase_currency": normalized_currency,
            "underlying_ticker": resolved_underlying,
            "byma_symbol": byma_symbol,
            "cedear_ratio": ratio_value,
            "cedear_ratio_source": ratio_source,
            "notes": notes.strip(),
        }

    def _cost_basis(self, position: PositionRecord, snapshot, selected_house: str) -> tuple[float, float]:
        notional = position.quantity * position.purchase_price

        # Use FX stored from Balanz extract when available — argentinadatos.com
        # doesn't always have rates for older dates, so the stored value is more
        # reliable for historical positions.
        if position.instrument_type == "cedear" and position.purchase_currency == "ARS":
            purchase_fx = position.purchase_ccl or snapshot.purchase_exchange.ccl
        else:
            stored_fx = _pick_stored_fx(position, selected_house)
            purchase_fx = stored_fx or _pick_fx(snapshot.purchase_exchange, selected_house)

        if position.purchase_currency == "ARS":
            cost_basis_ars = notional
            cost_basis_usd = notional / purchase_fx
        else:
            cost_basis_usd = notional
            cost_basis_ars = notional * purchase_fx
        return cost_basis_ars, cost_basis_usd

    def _benchmark_comparisons(
        self,
        cost_basis_ars: float,
        current_value_ars: float,
        snapshot,
    ) -> list[BenchmarkComparison]:
        tracked_values = {
            "official_usd": _fx_track(
                cost_basis_ars,
                snapshot.purchase_exchange.official,
                snapshot.current_exchange.official,
            ),
            "mep_usd": _fx_track(
                cost_basis_ars,
                snapshot.purchase_exchange.mep,
                snapshot.current_exchange.mep,
            ),
            "ccl_usd": _fx_track(
                cost_basis_ars,
                snapshot.purchase_exchange.ccl,
                snapshot.current_exchange.ccl,
            ),
            "inflation": cost_basis_ars * snapshot.inflation_factor,
            "plazo_fijo": cost_basis_ars * snapshot.fixed_term_factor,
        }
        comparisons = []
        for label, tracked_value in tracked_values.items():
            comparisons.append(
                BenchmarkComparison(
                    label=label,
                    tracked_value_ars=round(tracked_value, 2),
                    outperformance_ars=round(current_value_ars - tracked_value, 2),
                    outperformance_pct=round(_safe_return(current_value_ars, tracked_value), 4),
                )
            )
        return comparisons

    def _latest_close(self, ticker: str) -> tuple[float, date]:
        normalized_ticker = normalize_quote_symbol(ticker)
        cached = self._quote_cache.get(normalized_ticker)
        if cached is not None:
            return cached

        try:
            import yfinance as yf
        except ModuleNotFoundError as exc:
            raise PortfolioError("yfinance no esta instalado para valuar posiciones.") from exc

        frame = yf.download(
            to_market_data_symbol(normalized_ticker),
            period="10d",
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
        if frame.empty:
            raise PortfolioError(f"No se pudo obtener precio reciente para {normalized_ticker}.")
        if isinstance(frame.columns, pd.MultiIndex):
            frame.columns = frame.columns.get_level_values(0)
        frame.columns = [str(column).title() for column in frame.columns]
        frame.columns.name = None
        frame = frame.loc[:, ~pd.Index(frame.columns).duplicated(keep="first")]
        frame = frame.apply(pd.to_numeric, errors="coerce").dropna()
        if "Close" not in frame.columns or frame.empty:
            raise PortfolioError(f"Datos invalidos para {normalized_ticker}.")

        latest_row = frame.iloc[-1]
        latest_index = frame.index[-1]
        quote = (float(latest_row["Close"]), pd.Timestamp(latest_index).date())
        if len(frame) >= 2:
            prev_close = float(frame.iloc[-2]["Close"])
            self._prev_close_cache.set(normalized_ticker, prev_close)
        return self._quote_cache.set(normalized_ticker, quote)

    def _daily_change_pct(self, ticker: str) -> float:
        """Return today's price change vs yesterday's close as a fraction (e.g. 0.014 = +1.4%).

        Returns 0.0 when data is unavailable so callers never get an exception.
        _latest_close must have been called for this ticker first (populates prev cache).
        """
        normalized_ticker = normalize_quote_symbol(ticker)
        current = self._quote_cache.get(normalized_ticker)
        prev = self._prev_close_cache.get(normalized_ticker)
        if current is None or prev is None or prev == 0:
            return 0.0
        return (current[0] - prev) / prev

    def _ensure_schema(self) -> None:
        with connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    instrument_type TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    underlying_ticker TEXT NOT NULL,
                    byma_symbol TEXT,
                    cedear_ratio REAL,
                    cedear_ratio_source TEXT,
                    quantity REAL NOT NULL,
                    purchase_date TEXT NOT NULL,
                    purchase_price REAL NOT NULL,
                    purchase_currency TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_positions_user_id ON positions(user_id);
                """
            )
            # Sprint 6.1b: optional FX columns captured at purchase-date from
            # the Balanz extract. Use ALTER TABLE IF NOT EXISTS pattern so
            # existing DBs migrate forward without losing data.
            # SQLite doesn't have ALTER TABLE IF NOT EXISTS — we check pragma.
            existing_cols = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(positions)").fetchall()
            }
            for new_col in ("purchase_ccl", "purchase_mep", "purchase_official"):
                if new_col not in existing_cols:
                    conn.execute(f"ALTER TABLE positions ADD COLUMN {new_col} REAL")


def _extract_latest_close(frame: pd.DataFrame, symbol: str) -> tuple[float, date] | None:
    """Pull (close, date) out of a yfinance frame slice.

    Accepts both the per-ticker sub-frame from a multi-ticker download and
    the flat frame from a single-ticker download. Mirrors the cleaning that
    ``PortfolioService._latest_close`` does so the cached value has identical
    shape regardless of which path warmed it.
    """
    if frame is None or getattr(frame, "empty", True):
        return None

    sub = frame.copy()
    if isinstance(sub.columns, pd.MultiIndex):
        sub.columns = sub.columns.get_level_values(0)
    sub.columns = [str(column).title() for column in sub.columns]
    sub.columns.name = None
    sub = sub.loc[:, ~pd.Index(sub.columns).duplicated(keep="first")]
    sub = sub.apply(pd.to_numeric, errors="coerce").dropna()
    if "Close" not in sub.columns or sub.empty:
        return None
    latest_row = sub.iloc[-1]
    latest_index = sub.index[-1]
    return (float(latest_row["Close"]), pd.Timestamp(latest_index).date())


def _record_from_row(row) -> PositionRecord:
    keys = set(row.keys()) if hasattr(row, "keys") else set()
    return PositionRecord(
        position_id=int(row["id"]),
        user_id=int(row["user_id"]),
        instrument_type=str(row["instrument_type"]),
        symbol=str(row["symbol"]),
        underlying_ticker=str(row["underlying_ticker"]),
        byma_symbol=str(row["byma_symbol"]) if row["byma_symbol"] else None,
        cedear_ratio=float(row["cedear_ratio"]) if row["cedear_ratio"] is not None else None,
        cedear_ratio_source=str(row["cedear_ratio_source"]) if row["cedear_ratio_source"] else None,
        quantity=float(row["quantity"]),
        purchase_date=date.fromisoformat(str(row["purchase_date"])),
        purchase_price=float(row["purchase_price"]),
        purchase_currency=str(row["purchase_currency"]),
        notes=str(row["notes"]),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        updated_at=datetime.fromisoformat(str(row["updated_at"])),
        purchase_ccl=float(row["purchase_ccl"]) if "purchase_ccl" in keys and row["purchase_ccl"] is not None else None,
        purchase_mep=float(row["purchase_mep"]) if "purchase_mep" in keys and row["purchase_mep"] is not None else None,
        purchase_official=float(row["purchase_official"]) if "purchase_official" in keys and row["purchase_official"] is not None else None,
    )


def _normalize_benchmark_preference(benchmark_preference: str) -> str:
    normalized = benchmark_preference.strip().lower()
    if normalized not in {"official", "mep", "ccl"}:
        return "mep"
    return normalized


def _pick_fx(exchange_rates, benchmark_preference: str) -> float:
    if benchmark_preference == "official":
        return exchange_rates.official
    if benchmark_preference == "ccl":
        return exchange_rates.ccl
    return exchange_rates.mep


def _pick_stored_fx(position, selected_house: str) -> float | None:
    """Return the purchase-date FX stored on the position (from Balanz extract), or None."""
    if selected_house == "official":
        return position.purchase_official
    if selected_house == "ccl":
        return position.purchase_ccl
    return position.purchase_mep


def _fx_track(initial_ars: float, purchase_fx: float, current_fx: float) -> float:
    if purchase_fx <= 0 or current_fx <= 0:
        return initial_ars
    return (initial_ars / purchase_fx) * current_fx


def _safe_return(current_value: float, reference_value: float) -> float:
    if reference_value <= 0:
        return 0.0
    return (current_value / reference_value) - 1


def _aggregate_real_return(positions: list[PositionValuation]) -> float:
    if not positions:
        return 0.0
    total_current = sum(item.current_value_ars for item in positions)
    total_inflation_track = 0.0
    for item in positions:
        inflation_line = next(
            comparison for comparison in item.benchmark_comparisons if comparison.label == "inflation"
        )
        total_inflation_track += inflation_line.tracked_value_ars
    return _safe_return(total_current, total_inflation_track)


# Map the user-facing `benchmark_preference` (the FX they care about) to the
# label used inside each BenchmarkComparison record. This is the bridge
# between profile config and the math layer.
PREFERENCE_TO_COMPARISON_LABEL = {
    "official": "official_usd",
    "mep": "mep_usd",
    "ccl": "ccl_usd",
}


def _aggregate_preferred_benchmark_return(
    positions: list[PositionValuation],
    benchmark_preference: str,
) -> float:
    """Aggregate "did the portfolio beat the chosen FX benchmark?" across positions.

    Independent from `_aggregate_real_return` (which is canonical vs-inflation).
    This answers the question every Argentinian retail investor actually has:
    "Comparado contra el dólar que me importa, ¿gané o perdí?".
    """
    if not positions:
        return 0.0
    label = PREFERENCE_TO_COMPARISON_LABEL.get(benchmark_preference.strip().lower())
    if not label:
        return 0.0
    total_current = sum(item.current_value_ars for item in positions)
    total_tracked = 0.0
    for item in positions:
        line = next(
            (cmp for cmp in item.benchmark_comparisons if cmp.label == label),
            None,
        )
        if line is None:
            continue
        total_tracked += line.tracked_value_ars
    return _safe_return(total_current, total_tracked)


def _position_preferred_benchmark_return(
    valuation: PositionValuation,
    benchmark_preference: str,
) -> float:
    """Per-position version of the above. Used when populating each row."""
    label = PREFERENCE_TO_COMPARISON_LABEL.get(benchmark_preference.strip().lower())
    if not label:
        return 0.0
    line = next(
        (cmp for cmp in valuation.benchmark_comparisons if cmp.label == label),
        None,
    )
    if line is None:
        return 0.0
    return _safe_return(valuation.current_value_ars, line.tracked_value_ars)
