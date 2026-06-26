"""Tests for the weight-based portfolio backtest (V2.0 spec M2 #2).

swing.py strategies produce a [date, symbol, target_weight] panel. portfolio_backtest
simulates holding those weights (prior-day weights applied to today's returns — no
lookahead), charges turnover cost, and returns a portfolio equity curve + metrics.
run_strategy_backtest adapts any object with generate_signals(market_data) into it.
"""

import datetime as dt

import pandas as pd
import pytest

from stocks.services.quant.backtest.engine import BacktestConfig
from stocks.services.quant.backtest.portfolio import portfolio_backtest, run_strategy_backtest

D = dt.date


def _dates(n):
    return [D(2023, 1, 1) + dt.timedelta(days=i) for i in range(n)]


def _prices():
    # A rises 10%/day, B flat.
    d = _dates(3)
    rows = []
    for date, a, b in zip(d, [100, 110, 121], [100, 100, 100]):
        rows.append({"date": date, "symbol": "A", "close": a})
        rows.append({"date": date, "symbol": "B", "close": b})
    return pd.DataFrame(rows)


def _weights(wa=0.5, wb=0.5):
    rows = []
    for date in _dates(3):
        rows.append({"date": date, "symbol": "A", "target_weight": wa})
        rows.append({"date": date, "symbol": "B", "target_weight": wb})
    return pd.DataFrame(rows)


def test_portfolio_equity_and_return():
    res = portfolio_backtest(_weights(), _prices())
    # 50/50, A +10%/day, B flat -> +5%/day. 100k -> 105k -> 110.25k.
    assert res.equity_curve[0] == pytest.approx(100000.0)
    assert res.equity_curve[-1] == pytest.approx(110250.0)
    assert res.metrics.total_return == pytest.approx(0.1025)


def test_initial_turnover_is_full_weight():
    res = portfolio_backtest(_weights(), _prices())
    assert res.turnover[0] == pytest.approx(1.0)  # 0 -> (0.5 + 0.5)


def test_costs_reduce_final_equity():
    free = portfolio_backtest(_weights(), _prices())
    costed = portfolio_backtest(_weights(), _prices(), config=BacktestConfig(cost_bps=100))
    assert costed.equity_curve[-1] < free.equity_curve[-1]


def test_concentration_changes_return():
    # 100% in A (the riser) -> +10%/day -> total 21%.
    res = portfolio_backtest(_weights(wa=1.0, wb=0.0), _prices())
    assert res.metrics.total_return == pytest.approx(0.21)


def test_run_strategy_backtest_adapter():
    class StubStrategy:
        def generate_signals(self, market_data):
            return _weights()

    market_data = _prices()
    adapted = run_strategy_backtest(StubStrategy(), market_data)
    direct = portfolio_backtest(_weights(), _prices())
    assert adapted.equity_curve == direct.equity_curve


def _panel(symbols, n=80, start=D(2022, 1, 3)):
    """Deterministic long-format OHLCV panel for integration tests (no randomness)."""
    rows = []
    for si, sym in enumerate(symbols):
        price = 100.0 + si * 10
        for i in range(n):
            price *= 1 + 0.01 * (((i + si) % 5) - 1.5) / 3  # mild zig-zag drift
            c = round(price, 2)
            rows.append({
                "date": start + dt.timedelta(days=i), "symbol": sym,
                "open": c, "high": round(c * 1.01, 2), "low": round(c * 0.99, 2),
                "close": c, "volume": 100_000,
            })
    return pd.DataFrame(rows)


def test_real_swing_strategy_runs_end_to_end():
    # Wire a real swing.py strategy through the portfolio engine on a synthetic panel.
    from stocks.services.strategies.registry import get_strategy

    market_data = _panel(["AAA", "BBB", "CCC"], n=80)
    strat = get_strategy("minervini").make(force_market_ok=True)

    res = run_strategy_backtest(strat, market_data)
    # One equity point per unique date; result is well-formed (no crash, real metrics).
    assert len(res.equity_curve) == 80
    assert isinstance(res.metrics.total_return, float)
    assert isinstance(res.metrics.max_drawdown, float)
