"""Pure trade-journal analytics: realized P&L, R-multiple, and per-setup auto-review.

Decoupled from the ORM — operates on plain ``ClosedTrade`` records so it is trivially
testable and reusable. ``side`` is ``"LONG"`` or ``"SHORT"``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ClosedTrade:
    setup: str
    side: str
    entry: float
    stop: float
    exit: float
    qty: float
    fees: float = 0.0


@dataclass(frozen=True)
class SetupStats:
    setup: str
    trades: int
    wins: int
    win_rate: float
    total_pnl: float
    avg_pnl: float
    avg_r: float            # mean R-multiple over trades with a defined R
    expectancy_r: float     # expectancy expressed in R (== avg_r)


def _is_long(side: str) -> bool:
    return side.upper() != "SHORT"


def realized_pnl(trade: ClosedTrade) -> float:
    """Net realized P&L in currency, fees deducted."""
    gross = (trade.exit - trade.entry) if _is_long(trade.side) else (trade.entry - trade.exit)
    return gross * trade.qty - trade.fees


def return_pct(trade: ClosedTrade) -> float:
    """Fractional return on the entry price (sign-aware for shorts)."""
    if trade.entry <= 0:
        return 0.0
    move = (trade.exit - trade.entry) if _is_long(trade.side) else (trade.entry - trade.exit)
    return move / trade.entry


def r_multiple(trade: ClosedTrade) -> float | None:
    """Reward-to-initial-risk multiple, or None when the planned risk is non-positive."""
    risk = (trade.entry - trade.stop) if _is_long(trade.side) else (trade.stop - trade.entry)
    if risk <= 0:
        return None
    reward = (trade.exit - trade.entry) if _is_long(trade.side) else (trade.entry - trade.exit)
    return reward / risk


def review_by_setup(trades: Sequence[ClosedTrade]) -> dict[str, SetupStats]:
    """Group closed trades by setup and compute win rate, P&L, and expectancy-in-R."""
    by_setup: dict[str, list[ClosedTrade]] = {}
    for t in trades:
        by_setup.setdefault(t.setup, []).append(t)

    review: dict[str, SetupStats] = {}
    for setup, group in by_setup.items():
        n = len(group)
        pnls = [realized_pnl(t) for t in group]
        wins = sum(1 for p in pnls if p > 0)
        rs = [r for r in (r_multiple(t) for t in group) if r is not None]
        avg_r = sum(rs) / len(rs) if rs else 0.0
        review[setup] = SetupStats(
            setup=setup,
            trades=n,
            wins=wins,
            win_rate=wins / n if n else 0.0,
            total_pnl=sum(pnls),
            avg_pnl=sum(pnls) / n if n else 0.0,
            avg_r=avg_r,
            expectancy_r=avg_r,
        )
    return review
