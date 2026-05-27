from __future__ import annotations

import pandas as pd

from ..contracts import BacktestSummary
from ..contracts import Horizon
from ..indicators import compute_indicators
from ..signals import generate_deterministic_signal


def run_long_only_backtest(
    frame: pd.DataFrame,
    horizon: Horizon,
    starting_cash: float = 10_000.0,
    entry_threshold: float = 60.0,
    fee_bps: float = 10.0,
    slippage_bps: float = 5.0,
) -> BacktestSummary:
    enriched = compute_indicators(frame)
    if len(enriched) < 3:
        return BacktestSummary(
            strategy_name="directional_baseline",
            execution_model="next_open_fill_with_costs",
            starting_cash=starting_cash,
            ending_cash=starting_cash,
            total_return_pct=0.0,
            max_drawdown_pct=0.0,
            total_trades=0,
            win_rate_pct=0.0,
            expectancy=0.0,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
        )

    cash = starting_cash
    equity_curve = [starting_cash]
    trade_pnls: list[float] = []
    position_size = 0
    entry_price = 0.0
    position_side = 0
    stop_loss = None
    take_profit = None
    entry_index = None

    # The signal is computed on data up to bar i and filled on bar i+1 open.
    for i in range(len(enriched) - 1):
        current_slice = enriched.iloc[: i + 1]
        current_row = enriched.iloc[i]
        next_row = enriched.iloc[i + 1]

        if position_size == 0:
            signal = generate_deterministic_signal(current_slice, horizon)
            if signal.score >= entry_threshold and signal.direction.value in {"long", "short"}:
                raw_fill_price = float(next_row["Open"])
                fill_price = _apply_slippage(
                    raw_fill_price,
                    is_entry=True,
                    position_side=1 if signal.direction.value == "long" else -1,
                    slippage_bps=slippage_bps,
                )
                if fill_price <= 0:
                    continue
                position_size = max(1, int(cash / fill_price))
                position_side = 1 if signal.direction.value == "long" else -1
                gross_notional = position_size * fill_price
                cash -= _entry_cash_impact(gross_notional, position_side)
                cash -= _transaction_cost(gross_notional, fee_bps)
                entry_price = fill_price
                stop_loss = signal.stop_loss
                take_profit = signal.take_profit
                entry_index = i + 1
            equity_curve.append(
                _mark_to_market(cash, position_size, float(next_row["Close"]), position_side)
            )
            continue

        low_price = float(current_row["Low"])
        high_price = float(current_row["High"])
        close_price = float(current_row["Close"])
        exit_reason = None
        exit_price = close_price

        if position_side == 1:
            if stop_loss is not None and low_price <= stop_loss:
                exit_reason = "stop_loss"
                exit_price = float(stop_loss)
            elif take_profit is not None and high_price >= take_profit:
                exit_reason = "take_profit"
                exit_price = float(take_profit)
        else:
            if stop_loss is not None and high_price >= stop_loss:
                exit_reason = "stop_loss"
                exit_price = float(stop_loss)
            elif take_profit is not None and low_price <= take_profit:
                exit_reason = "take_profit"
                exit_price = float(take_profit)

        signal = generate_deterministic_signal(current_slice, horizon)
        if exit_reason is None:
            expected_direction = "long" if position_side == 1 else "short"
            if signal.direction.value != expected_direction:
                exit_reason = "signal_flip"
                exit_price = close_price

        if exit_reason is not None and entry_index is not None and position_side != 0:
            realized_exit = _apply_slippage(
                exit_price,
                is_entry=False,
                position_side=position_side,
                slippage_bps=slippage_bps,
            )
            gross_notional = position_size * realized_exit
            cash += _exit_cash_impact(gross_notional, position_side)
            cash -= _transaction_cost(gross_notional, fee_bps)
            pnl = (realized_exit - entry_price) * position_size * position_side
            trade_pnls.append(pnl)
            position_size = 0
            entry_price = 0.0
            position_side = 0
            stop_loss = None
            take_profit = None
            entry_index = None

        equity_curve.append(_mark_to_market(cash, position_size, close_price, position_side))

    if position_size > 0:
        final_close = float(enriched.iloc[-1]["Close"])
        realized_exit = _apply_slippage(
            final_close,
            is_entry=False,
            position_side=position_side,
            slippage_bps=slippage_bps,
        )
        gross_notional = position_size * realized_exit
        cash += _exit_cash_impact(gross_notional, position_side)
        cash -= _transaction_cost(gross_notional, fee_bps)
        pnl = (realized_exit - entry_price) * position_size * position_side
        trade_pnls.append(pnl)
        equity_curve.append(cash)

    return _build_summary(starting_cash, cash, equity_curve, trade_pnls, fee_bps, slippage_bps)


def _build_summary(
    starting_cash: float,
    ending_cash: float,
    equity_curve: list[float],
    trade_pnls: list[float],
    fee_bps: float,
    slippage_bps: float,
) -> BacktestSummary:
    max_drawdown_pct = _max_drawdown(equity_curve)
    total_return_pct = ((ending_cash - starting_cash) / starting_cash) * 100
    winning_trades = [trade for trade in trade_pnls if trade > 0]
    win_rate_pct = (len(winning_trades) / len(trade_pnls) * 100) if trade_pnls else 0.0
    expectancy = (sum(trade_pnls) / len(trade_pnls)) if trade_pnls else 0.0

    return BacktestSummary(
        strategy_name="directional_baseline",
        execution_model="next_open_fill_with_costs",
        starting_cash=round(starting_cash, 2),
        ending_cash=round(ending_cash, 2),
        total_return_pct=round(total_return_pct, 2),
        max_drawdown_pct=round(max_drawdown_pct, 2),
        total_trades=len(trade_pnls),
        win_rate_pct=round(win_rate_pct, 2),
        expectancy=round(expectancy, 2),
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
    )


def _mark_to_market(cash: float, position_size: int, last_price: float, position_side: int) -> float:
    if position_side == 1:
        return cash + (position_size * last_price)
    if position_side == -1:
        return cash - (position_size * last_price)
    return cash


def _transaction_cost(gross_notional: float, fee_bps: float) -> float:
    return gross_notional * (fee_bps / 10_000)


def _apply_slippage(price: float, is_entry: bool, position_side: int, slippage_bps: float) -> float:
    direction = 1 if position_side == 1 else -1
    if is_entry:
        multiplier = 1 + ((slippage_bps / 10_000) * direction)
    else:
        multiplier = 1 - ((slippage_bps / 10_000) * direction)
    return price * multiplier


def _entry_cash_impact(gross_notional: float, position_side: int) -> float:
    return gross_notional if position_side == 1 else -gross_notional


def _exit_cash_impact(gross_notional: float, position_side: int) -> float:
    return gross_notional if position_side == 1 else -gross_notional


def _max_drawdown(equity_curve: list[float]) -> float:
    peak = equity_curve[0]
    worst_drawdown = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        if peak == 0:
            continue
        drawdown = ((peak - equity) / peak) * 100
        worst_drawdown = max(worst_drawdown, drawdown)
    return worst_drawdown
