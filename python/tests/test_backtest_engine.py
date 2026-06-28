"""Tests for the single-name backtest engine (V2.0 spec M2).

Deterministic, no-lookahead, long-only event simulation: entries fill at the NEXT bar's
open; while in a position, intrabar stop/target are checked against the bar's low/high
(stop first, conservative). Costs/slippage are applied in basis points. All scenarios use
synthetic bars with hand-computable outcomes.
"""

import datetime as dt

import pandas as pd
import pytest

from stocks.services.quant.backtest.engine import BacktestConfig, run_backtest

D = dt.date


def _bars(rows):
    """rows: list of (date, open, high, low, close)."""
    return pd.DataFrame(
        [{"trading_date": d, "open": o, "high": h, "low": low, "close": c} for (d, o, h, low, c) in rows]
    )


def _signals(n, true_at):
    return [i in true_at for i in range(n)]


def test_empty_bars_returns_empty_result():
    result = run_backtest(_bars([]), entries=[])
    assert result.trades == []
    assert result.equity_curve == []
    assert result.metrics.trades == 0


def test_no_entries_gives_flat_equity_and_no_trades():
    bars = _bars([
        (D(2023, 1, 2), 100, 101, 99, 100),
        (D(2023, 1, 3), 100, 102, 98, 101),
    ])
    result = run_backtest(bars, entries=[False, False])
    assert result.trades == []
    assert result.equity_curve[0] == result.equity_curve[-1]  # flat
    assert result.metrics.total_return == 0.0


def test_entry_fills_at_next_bar_open_no_lookahead():
    # Entry signal only on the LAST bar -> no following bar to fill -> no trade.
    bars = _bars([
        (D(2023, 1, 2), 100, 101, 99, 100),
        (D(2023, 1, 3), 100, 102, 98, 101),
    ])
    result = run_backtest(bars, entries=[False, True])
    assert result.trades == []


def test_target_hit_intrabar():
    bars = _bars([
        (D(2023, 1, 2), 100, 100, 100, 100),   # entry signal here
        (D(2023, 1, 3), 100, 102, 99, 101),    # fill at open=100; target 110 not hit
        (D(2023, 1, 4), 101, 112, 100, 108),   # high 112 >= 110 -> exit at target 110
    ])
    result = run_backtest(bars, entries=_signals(3, {0}), target_pct=0.10)
    assert len(result.trades) == 1
    t = result.trades[0]
    assert t.entry_price == pytest.approx(100.0)
    assert t.exit_price == pytest.approx(110.0)
    assert t.reason == "TARGET"
    assert t.return_pct == pytest.approx(0.10)


def test_stop_hit_intrabar():
    bars = _bars([
        (D(2023, 1, 2), 100, 100, 100, 100),   # entry signal
        (D(2023, 1, 3), 100, 101, 94, 96),     # fill 100; low 94 <= stop 95 -> exit 95
    ])
    result = run_backtest(bars, entries=_signals(2, {0}), stop_pct=0.05)
    assert len(result.trades) == 1
    assert result.trades[0].reason == "STOP"
    assert result.trades[0].return_pct == pytest.approx(-0.05)


def test_stop_checked_before_target_when_both_in_range():
    # A bar that spans both stop and target -> conservative engine takes the stop.
    bars = _bars([
        (D(2023, 1, 2), 100, 100, 100, 100),
        (D(2023, 1, 3), 100, 115, 90, 100),   # both stop(95) and target(110) inside range
    ])
    result = run_backtest(bars, entries=_signals(2, {0}), stop_pct=0.05, target_pct=0.10)
    assert result.trades[0].reason == "STOP"


def test_exit_signal_closes_at_close():
    bars = _bars([
        (D(2023, 1, 2), 100, 100, 100, 100),   # entry signal
        (D(2023, 1, 3), 100, 105, 99, 104),    # fill 100
        (D(2023, 1, 4), 104, 107, 103, 106),   # exit signal -> close at 106
    ])
    result = run_backtest(bars, entries=_signals(3, {0}), exits=_signals(3, {2}))
    assert len(result.trades) == 1
    assert result.trades[0].exit_price == pytest.approx(106.0)
    assert result.trades[0].return_pct == pytest.approx(0.06)


def test_costs_reduce_return():
    bars = _bars([
        (D(2023, 1, 2), 100, 100, 100, 100),
        (D(2023, 1, 3), 100, 102, 99, 101),
        (D(2023, 1, 4), 101, 112, 100, 108),
    ])
    entries = _signals(3, {0})
    gross = run_backtest(bars, entries=entries, target_pct=0.10)
    net = run_backtest(bars, entries=entries, target_pct=0.10, config=BacktestConfig(cost_bps=10))
    assert net.trades[0].return_pct < gross.trades[0].return_pct
    assert net.trades[0].return_pct == pytest.approx(0.10, abs=0.01)  # ~9.8%, near but below


def test_open_position_marked_to_market():
    bars = _bars([
        (D(2023, 1, 2), 100, 100, 100, 100),   # entry signal
        (D(2023, 1, 3), 100, 120, 100, 120),   # in position, close 120, no exit -> MTM up ~20%
    ])
    result = run_backtest(bars, entries=_signals(2, {0}))  # never exits
    assert result.trades == []  # still open at end
    assert result.equity_curve[-1] == pytest.approx(result.equity_curve[0] * 1.20, rel=1e-6)


def test_reproducible():
    bars = _bars([
        (D(2023, 1, 2), 100, 100, 100, 100),
        (D(2023, 1, 3), 100, 102, 99, 101),
        (D(2023, 1, 4), 101, 112, 100, 108),
    ])
    entries = _signals(3, {0})
    r1 = run_backtest(bars, entries=entries, target_pct=0.10)
    r2 = run_backtest(bars, entries=entries, target_pct=0.10)
    assert r1.metrics == r2.metrics
    assert [t.return_pct for t in r1.trades] == [t.return_pct for t in r2.trades]
