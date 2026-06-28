"""Pure, reproducible performance metrics for the backtest engine.

Every function is a deterministic function of its inputs and is unit-tested against
hand-computed values. Degenerate inputs (no trades, no losses, zero variance) return
explicit, honest values (0.0 or inf) — never a fabricated default.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


def total_return(equity_curve: Sequence[float]) -> float:
    """Fractional return from first to last equity value (0.0 if <2 points or start<=0)."""
    if len(equity_curve) < 2 or equity_curve[0] <= 0:
        return 0.0
    return equity_curve[-1] / equity_curve[0] - 1.0


def cagr(equity_curve: Sequence[float], years: float) -> float:
    """Compound annual growth rate over ``years`` (0.0 if years<=0 or <2 points)."""
    if len(equity_curve) < 2 or years <= 0 or equity_curve[0] <= 0:
        return 0.0
    return (equity_curve[-1] / equity_curve[0]) ** (1.0 / years) - 1.0


def max_drawdown(equity_curve: Sequence[float]) -> float:
    """Largest peak-to-trough decline as a positive fraction (0.0 if never declines)."""
    if len(equity_curve) < 2:
        return 0.0
    peak = equity_curve[0]
    worst = 0.0
    for value in equity_curve:
        if value > peak:
            peak = value
        if peak > 0:
            drawdown = (peak - value) / peak
            if drawdown > worst:
                worst = drawdown
    return worst


def win_rate(trade_returns: Sequence[float]) -> float:
    """Fraction of trades with a positive return (0.0 if there are no trades)."""
    if not trade_returns:
        return 0.0
    wins = sum(1 for r in trade_returns if r > 0)
    return wins / len(trade_returns)


def profit_factor(trade_returns: Sequence[float]) -> float:
    """Gross gains / gross losses. inf if there are gains but no losses; 0.0 if no gains."""
    gains = sum(r for r in trade_returns if r > 0)
    losses = -sum(r for r in trade_returns if r < 0)
    if losses == 0:
        return math.inf if gains > 0 else 0.0
    return gains / losses


def sharpe_ratio(
    period_returns: Sequence[float],
    periods_per_year: int = 252,
    risk_free: float = 0.0,
) -> float:
    """Annualized Sharpe ratio from per-period returns.

    Returns 0.0 when there are fewer than two returns or the returns have zero variance
    (an undefined Sharpe is reported honestly as 0.0, not a placeholder).
    """
    n = len(period_returns)
    if n < 2:
        return 0.0
    rf_per_period = risk_free / periods_per_year
    excess = [r - rf_per_period for r in period_returns]
    mean = sum(excess) / n
    variance = sum((x - mean) ** 2 for x in excess) / (n - 1)  # sample variance
    if variance <= 0:
        return 0.0
    return (mean / math.sqrt(variance)) * math.sqrt(periods_per_year)


@dataclass(frozen=True)
class BacktestMetrics:
    total_return: float
    cagr: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    trades: int


def compute_metrics(
    equity_curve: Sequence[float],
    trade_returns: Sequence[float],
    years: float,
    periods_per_year: int = 252,
    risk_free: float = 0.0,
) -> BacktestMetrics:
    """Compute the full metric set from an equity curve and per-trade returns.

    Deterministic: identical inputs produce an identical, equality-comparable result.
    """
    period_returns = [
        equity_curve[i] / equity_curve[i - 1] - 1.0
        for i in range(1, len(equity_curve))
        if equity_curve[i - 1] > 0
    ]
    return BacktestMetrics(
        total_return=total_return(equity_curve),
        cagr=cagr(equity_curve, years),
        max_drawdown=max_drawdown(equity_curve),
        win_rate=win_rate(trade_returns),
        profit_factor=profit_factor(trade_returns),
        sharpe_ratio=sharpe_ratio(period_returns, periods_per_year, risk_free),
        trades=len(trade_returns),
    )
