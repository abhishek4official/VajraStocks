"""Tests for run_symbol_backtest — the BarStore -> signals -> engine adapter (M2 #1).

This is the end-to-end "setup replay": read adjusted bars for a symbol from the columnar
data plane, generate signals, and run the deterministic engine.
"""

import datetime as dt

import pandas as pd
import pytest

from stocks.data.bar_store import BarStore
from stocks.services.quant.backtest.replay import run_symbol_backtest
from stocks.services.quant.backtest.signals import sma_crossover_signals

D = dt.date


@pytest.fixture
def store(tmp_path):
    return BarStore(tmp_path / "columnar")


def _ohlc(closes):
    return pd.DataFrame(
        [
            {
                "trading_date": D(2023, 1, 1) + dt.timedelta(days=i),
                "open": c, "high": c, "low": c, "close": c, "adj_close": c, "volume": 1000,
            }
            for i, c in enumerate(closes)
        ]
    )


def _sma(bars):
    return sma_crossover_signals(bars, fast=2, slow=3)


def test_missing_symbol_returns_empty_result(store):
    res = run_symbol_backtest(store, "NOPE", _sma)
    assert res.trades == []
    assert res.equity_curve == []
    assert res.metrics.trades == 0


def test_end_to_end_single_trade(store):
    # SMA(2/3) crosses up at idx 3 -> fill at idx 4 open=14; exit signal at idx 6 -> close=10.
    store.write_bars("ACME", _ohlc([10, 10, 10, 12, 14, 12, 10, 9]))
    res = run_symbol_backtest(store, "ACME", _sma)
    assert len(res.trades) == 1
    assert res.trades[0].reason == "EXIT_SIGNAL"
    assert res.trades[0].entry_price == pytest.approx(14.0)
    assert res.trades[0].return_pct == pytest.approx(10 / 14 - 1)
    assert res.metrics.trades == 1


def test_adjusted_flows_through(store):
    # Raw series has a 2:1 split discontinuity at idx 4 (≈210 -> ≈106). On RAW data the SMA
    # sees a false crash; the split-adjusted series (pre-split halved) rises smoothly. So the
    # signals — and the equity curve — differ, proving adjusted=True/actions are forwarded.
    store.write_bars("ACME", _ohlc([200, 200, 205, 210, 106, 108, 110, 112]))
    actions = [{"action_date": D(2023, 1, 5), "action_type": "SPLIT", "value": 2.0}]

    raw = run_symbol_backtest(store, "ACME", _sma, adjusted=False)
    adj = run_symbol_backtest(store, "ACME", _sma, adjusted=True, actions=actions)
    assert adj.equity_curve != raw.equity_curve


def test_accepts_signal_name_from_registry(store):
    store.write_bars("ACME", _ohlc([10, 10, 10, 12, 14, 12, 10, 9]))
    # Passing a registered name resolves to the signal generator.
    res = run_symbol_backtest(store, "ACME", "breakout")
    assert res.metrics.trades >= 0  # runs end-to-end without error
