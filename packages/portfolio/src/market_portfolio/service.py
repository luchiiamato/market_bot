from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime

import pandas as pd

from market_bot.utils import TTLCache
from market_identity.store import connection
from market_reference import ArgentinaBenchmarkError, ArgentinaBenchmarkService

from .cedears import CedearReference, build_byma_symbol, resolve_cedear_reference
from .models import BenchmarkComparison, PortfolioSummary, PositionRecord, PositionValuation


class PortfolioError(RuntimeError):
    """Raised when portfolio operations cannot be completed."""


class PortfolioService:
    def __init__(self, benchmark_service: ArgentinaBenchmarkService | None = None) -> None:
        self.benchmark_service = benchmark_service or ArgentinaBenchmarkService()
        self._quote_cache: TTLCache[tuple[float, date]] = TTLCache(ttl_seconds=300)
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
    ) -> PositionValuation:
        normalized_type = instrument_type.strip().lower()
        if normalized_type not in {"stock", "cedear"}:
            raise PortfolioError("El tipo de instrumento debe ser stock o cedear.")
        if quantity <= 0 or purchase_price <= 0:
            raise PortfolioError("Cantidad y precio de compra deben ser positivos.")

        normalized_symbol = symbol.strip().upper()
        normalized_currency = purchase_currency.strip().upper()
        ratio_value = None
        ratio_source = None
        byma_symbol = None
        resolved_underlying = (underlying_ticker or normalized_symbol).strip().upper()

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
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    normalized_type,
                    normalized_symbol,
                    resolved_underlying,
                    byma_symbol,
                    ratio_value,
                    ratio_source,
                    quantity,
                    purchase_date.isoformat(),
                    purchase_price,
                    normalized_currency,
                    notes.strip(),
                    now,
                    now,
                ),
            )
            position_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

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
        return [
            self._build_position_valuation(
                _record_from_row(row),
                benchmark_preference,
                risk_tolerance=risk_tolerance,
            )
            for row in rows
        ]

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
            positions=positions,
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
    ) -> PositionValuation:
        today = date.today()
        snapshot = self.benchmark_service.build_period_snapshot(position.purchase_date, today)
        selected_house = _normalize_benchmark_preference(benchmark_preference)
        current_fx = _pick_fx(snapshot.current_exchange, selected_house)

        notes: list[str] = []
        if position.instrument_type == "cedear":
            local_symbol = position.byma_symbol or build_byma_symbol(position.symbol)
            local_price_ars, quote_date = self._latest_close(local_symbol)
            underlying_price_usd, _ = self._latest_close(position.underlying_ticker)
            current_value_ars = position.quantity * local_price_ars
            # USD value for CEDEAR uses CCL conversion of the ARS market value.
            # This is robust against ratio inference errors: even if the stored
            # cedear_ratio is wrong, the USD figure still reflects what the user
            # would get by selling the CEDEARs and dollarizing through CCL.
            # The (qty / ratio) × underlying_price formula gave wildly wrong USD
            # when the ratio fell back to 1.0 or to a parity-snapped neighbor.
            current_ccl = snapshot.current_exchange.ccl
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
            benchmark_comparisons=comparisons,
            notes=notes,
        )

    def _cost_basis(self, position: PositionRecord, snapshot, selected_house: str) -> tuple[float, float]:
        notional = position.quantity * position.purchase_price
        if position.instrument_type == "cedear" and position.purchase_currency == "ARS":
            purchase_fx = snapshot.purchase_exchange.ccl
        else:
            purchase_fx = _pick_fx(snapshot.purchase_exchange, selected_house)

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
        normalized_ticker = ticker.strip().upper()
        cached = self._quote_cache.get(normalized_ticker)
        if cached is not None:
            return cached

        try:
            import yfinance as yf
        except ModuleNotFoundError as exc:
            raise PortfolioError("yfinance no esta instalado para valuar posiciones.") from exc

        frame = yf.download(
            normalized_ticker,
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
        return self._quote_cache.set(normalized_ticker, quote)

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


def _record_from_row(row) -> PositionRecord:
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
