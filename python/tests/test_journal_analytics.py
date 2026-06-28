"""Tests for trade-journal analytics (V2.0 spec M3).

Pure functions over closed-trade records — realized P&L, R-multiple, and the per-setup
auto-review (win rate / expectancy-in-R / R distribution). These answer the journal's
core question: "did my setups actually work?" — all computed, never fabricated.
"""

import pytest

from stocks.services.journal.analytics import (
    ClosedTrade,
    r_multiple,
    realized_pnl,
    return_pct,
    review_by_setup,
)


def _t(setup="pullback", side="LONG", entry=100.0, stop=95.0, exit=110.0, qty=10.0, fees=0.0):
    return ClosedTrade(setup=setup, side=side, entry=entry, stop=stop, exit=exit, qty=qty, fees=fees)


def test_realized_pnl_long_and_short():
    assert realized_pnl(_t(entry=100, exit=110, qty=10, fees=0)) == pytest.approx(100.0)
    assert realized_pnl(_t(side="SHORT", entry=100, exit=90, qty=10)) == pytest.approx(100.0)
    assert realized_pnl(_t(entry=100, exit=110, qty=10, fees=15)) == pytest.approx(85.0)  # fees deducted


def test_return_pct():
    assert return_pct(_t(entry=100, exit=110)) == pytest.approx(0.10)
    assert return_pct(_t(side="SHORT", entry=100, exit=90)) == pytest.approx(0.10)


def test_r_multiple_long():
    # risk = 100-95 = 5; reward = 110-100 = 10 -> R = 2.0
    assert r_multiple(_t(entry=100, stop=95, exit=110)) == pytest.approx(2.0)
    # a loss: exit 96 -> reward -4 -> R = -0.8
    assert r_multiple(_t(entry=100, stop=95, exit=96)) == pytest.approx(-0.8)


def test_r_multiple_short():
    assert r_multiple(_t(side="SHORT", entry=100, stop=105, exit=90)) == pytest.approx(2.0)


def test_r_multiple_undefined_when_no_risk():
    # stop at/above entry for a long -> non-positive risk -> undefined (None)
    assert r_multiple(_t(entry=100, stop=100, exit=110)) is None
    assert r_multiple(_t(entry=100, stop=105, exit=110)) is None


def test_review_by_setup():
    trades = [
        _t(setup="pullback", entry=100, stop=95, exit=110, qty=10),   # R=2.0, pnl=100, win
        _t(setup="pullback", entry=100, stop=95, exit=96, qty=10),    # R=-0.8, pnl=-40, loss
        _t(setup="breakout", entry=50, stop=45, exit=65, qty=10),     # R=3.0, pnl=150, win
    ]
    review = review_by_setup(trades)

    pb = review["pullback"]
    assert pb.trades == 2
    assert pb.wins == 1
    assert pb.win_rate == pytest.approx(0.5)
    assert pb.total_pnl == pytest.approx(60.0)
    assert pb.avg_r == pytest.approx(0.6)          # (2.0 + -0.8) / 2
    assert pb.expectancy_r == pytest.approx(0.6)   # mean R per trade

    bo = review["breakout"]
    assert bo.trades == 1
    assert bo.win_rate == 1.0
    assert bo.avg_r == pytest.approx(3.0)


def test_review_empty():
    assert review_by_setup([]) == {}
