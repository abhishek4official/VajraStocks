"""Weight-based portfolio backtest (V2.0 spec M2 #2) — wires swing.py strategies.

swing.py's ``generate_signals(market_data)`` returns a ``[date, symbol, target_weight]``
panel. This engine simulates holding those weights: the prior bar's weights earn the
current bar's returns (no lookahead), turnover is charged in basis points, and the result
is a portfolio equity curve + computed metrics.

``run_strategy_backtest`` adapts any object exposing ``generate_signals(market_data)`` —
including the real swing strategies — into the engine.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pandas as pd

from stocks.services.quant.backtest.engine import BacktestConfig, BacktestMetrics
from stocks.services.quant.backtest.metrics import compute_metrics


@dataclass(frozen=True)
class PortfolioResult:
    dates: list[dt.date]
    equity_curve: list[float]
    turnover: list[float]
    metrics: BacktestMetrics


def _as_date(value) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return pd.Timestamp(value).date()


def portfolio_backtest(
    weights: pd.DataFrame,
    prices: pd.DataFrame,
    *,
    config: BacktestConfig | None = None,
) -> PortfolioResult:
    """Backtest a target-weight panel against a price panel.

    ``weights``: columns [date, symbol, target_weight]. ``prices``: columns [date, symbol,
    close]. Dates come from the price panel; a symbol absent from a date's weights is held
    at weight 0. Returns a portfolio equity curve, per-date turnover, and metrics.
    """
    config = config or BacktestConfig()
    cost = config.cost_bps / 1e4

    px = prices.copy()
    px["date"] = px["date"].map(_as_date)
    close = px.pivot_table(index="date", columns="symbol", values="close").sort_index()
    returns = close.pct_change().fillna(0.0)

    w = weights.copy()
    w["date"] = w["date"].map(_as_date)
    W = (
        w.pivot_table(index="date", columns="symbol", values="target_weight")
        .reindex(index=close.index, columns=close.columns)
        .fillna(0.0)
    )

    prev_W = W.shift(1).fillna(0.0)
    port_ret = (prev_W * returns).sum(axis=1)
    turnover = (W - prev_W).abs().sum(axis=1)

    dates = list(close.index)
    equity_curve: list[float] = []
    equity = config.initial_capital
    for i in range(len(dates)):
        if i == 0:
            equity = config.initial_capital * (1.0 - cost * float(turnover.iloc[0]))
        else:
            net = float(port_ret.iloc[i]) - cost * float(turnover.iloc[i])
            equity = equity * (1.0 + net)
        equity_curve.append(equity)

    years = max((dates[-1] - dates[0]).days / 365.25, 0.0) if len(dates) >= 2 else 0.0
    metrics = compute_metrics(equity_curve=equity_curve, trade_returns=[], years=years)
    return PortfolioResult(
        dates=dates,
        equity_curve=equity_curve,
        turnover=[float(x) for x in turnover.tolist()],
        metrics=metrics,
    )


def run_strategy_backtest(
    strategy,
    market_data: pd.DataFrame,
    *,
    config: BacktestConfig | None = None,
) -> PortfolioResult:
    """Run a portfolio backtest for any strategy exposing generate_signals(market_data).

    ``market_data`` is the long-format price panel ([date, symbol, close, ...]) the strategy
    consumes; the strategy's ``target_weight`` output is backtested against the same closes.
    """
    signals = strategy.generate_signals(market_data)
    weights = signals[["date", "symbol", "target_weight"]]
    prices = market_data[["date", "symbol", "close"]]
    return portfolio_backtest(weights, prices, config=config)
