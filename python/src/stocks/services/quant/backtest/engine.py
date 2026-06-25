"""Single-name event-driven backtest engine (V2.0 spec M2).

Deterministic, no-lookahead, long-only. Contract:
- ``entries[i]`` is a signal known at the close of bar i; the position is opened at the
  NEXT bar's open (so no same-bar lookahead).
- While in a position each bar is checked intrabar against stop then target (stop first,
  conservative) using the bar's low/high; otherwise an ``exits[i]`` signal closes at that
  bar's close.
- Costs and slippage are applied in basis points on each fill.
- One position at a time; each trade deploys the full current equity (fractional shares),
  so returns compound. Risk-based sizing arrives when swing.py strategies are wired in.

The engine returns trades, a per-bar equity curve, and computed (never fabricated) metrics.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd

from stocks.services.quant.backtest.metrics import BacktestMetrics, compute_metrics


@dataclass(frozen=True)
class BacktestConfig:
    initial_capital: float = 100_000.0
    cost_bps: float = 0.0       # per-side commission/taxes, in basis points
    slippage_bps: float = 0.0   # per-side slippage, in basis points


@dataclass(frozen=True)
class Trade:
    entry_date: dt.date
    entry_price: float
    exit_date: dt.date
    exit_price: float
    qty: float
    return_pct: float
    reason: str  # "TARGET" | "STOP" | "EXIT_SIGNAL"


@dataclass(frozen=True)
class BacktestResult:
    trades: list[Trade]
    equity_curve: list[float]
    metrics: BacktestMetrics


def run_backtest(
    bars: pd.DataFrame,
    entries: Sequence[bool],
    *,
    stop_pct: float | None = None,
    target_pct: float | None = None,
    exits: Sequence[bool] | None = None,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """Run the long-only single-name backtest. See module docstring for the contract."""
    config = config or BacktestConfig()
    n = len(bars)
    if len(entries) != n:
        raise ValueError("entries must align 1:1 with bars")
    if exits is not None and len(exits) != n:
        raise ValueError("exits must align 1:1 with bars")

    o = bars["open"].tolist()
    h = bars["high"].tolist()
    low = bars["low"].tolist()
    c = bars["close"].tolist()
    dates = [_as_date(d) for d in bars["trading_date"].tolist()]

    slip = config.slippage_bps / 1e4
    cost = config.cost_bps / 1e4

    equity = config.initial_capital
    equity_curve: list[float] = []
    trades: list[Trade] = []

    in_position = False
    qty = 0.0
    entry_price = 0.0
    entry_date = dates[0]
    capital_before = equity
    pending_entry = False  # set when a signal fires; acted on at the next bar's open

    for i in range(n):
        # 1. Open a position queued by the previous bar's signal, at this bar's open.
        if pending_entry and not in_position:
            capital_before = equity
            fill = o[i] * (1 + slip)
            entry_cost = capital_before * cost
            qty = (capital_before - entry_cost) / fill
            entry_price = fill
            entry_date = dates[i]
            in_position = True
            pending_entry = False

        # 2. Exit check (intrabar) for any open position — including the entry bar, since
        #    the bar's low/high occur after the open and can hit the stop/target same day.
        if in_position:
            exit_price: float | None = None
            reason = ""
            stop_price = entry_price * (1 - stop_pct) if stop_pct is not None else None
            target_price = entry_price * (1 + target_pct) if target_pct is not None else None

            if stop_price is not None and low[i] <= stop_price:
                exit_price, reason = stop_price, "STOP"
            elif target_price is not None and h[i] >= target_price:
                exit_price, reason = target_price, "TARGET"
            elif exits is not None and exits[i]:
                exit_price, reason = c[i], "EXIT_SIGNAL"

            if exit_price is not None:
                fill = exit_price * (1 - slip)
                gross = qty * fill
                capital_after = gross - gross * cost
                trades.append(
                    Trade(
                        entry_date=entry_date,
                        entry_price=entry_price,
                        exit_date=dates[i],
                        exit_price=exit_price,
                        qty=qty,
                        return_pct=capital_after / capital_before - 1.0,
                        reason=reason,
                    )
                )
                equity = capital_after
                in_position = False
                qty = 0.0
            else:
                equity = qty * c[i]  # mark to market

        # 3. Queue an entry for the next bar if signalled and currently flat.
        if entries[i] and not in_position and not pending_entry:
            pending_entry = True

        equity_curve.append(equity)

    years = max((dates[-1] - dates[0]).days / 365.25, 0.0) if n >= 2 else 0.0
    metrics = compute_metrics(
        equity_curve=equity_curve,
        trade_returns=[t.return_pct for t in trades],
        years=years,
    )
    return BacktestResult(trades=trades, equity_curve=equity_curve, metrics=metrics)


def _as_date(value) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return pd.Timestamp(value).date()
