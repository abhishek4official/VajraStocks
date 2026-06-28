"""Tests for persisting backtest results (V2.0 spec M2).

A backtest run is stored with its params, computed metrics, and per-trade audit trail so
results are durable and listable. The capstone test proves *reproducibility on record*:
the stored metrics equal a fresh re-run — there are no constants, only computed values.
"""

import datetime as dt

import pytest

from stocks.data.bar_store import BarStore
from stocks.services.quant.backtest.engine import BacktestResult, Trade
from stocks.services.quant.backtest.metrics import compute_metrics
from stocks.services.quant.backtest.persistence import BacktestRepository
from stocks.services.quant.backtest.replay import run_symbol_backtest
from stocks.services.quant.backtest.signals import sma_crossover_signals

D = dt.date


def _ohlc(closes):
    import pandas as pd

    return pd.DataFrame(
        [
            {
                "trading_date": D(2023, 1, 1) + dt.timedelta(days=i),
                "open": c, "high": c, "low": c, "close": c, "adj_close": c, "volume": 1000,
            }
            for i, c in enumerate(closes)
        ]
    )


def _manual_result() -> BacktestResult:
    equity = [100000.0, 110000.0, 105000.0, 120000.0]
    trades = [
        Trade(D(2023, 1, 2), 100.0, D(2023, 1, 3), 110.0, 1000.0, 0.10, "TARGET"),
        Trade(D(2023, 1, 3), 110.0, D(2023, 1, 4), 104.5, 1000.0, -0.05, "STOP"),
    ]
    return BacktestResult(trades, equity, compute_metrics(equity, [0.10, -0.05], years=1.0))


def test_save_returns_id_and_persists_counts(db_session):
    repo = BacktestRepository(db_session)
    bid = repo.save(symbol="ACME", signal="manual", result=_manual_result())
    assert isinstance(bid, int)
    run = repo.get(bid)
    assert run.symbol == "ACME"
    assert run.trades_count == 2


def test_reloaded_metrics_match_saved(db_session):
    result = _manual_result()
    repo = BacktestRepository(db_session)
    bid = repo.save(symbol="ACME", signal="manual", result=result)

    stored = repo.get_metrics(bid)
    assert stored["total_return"] == pytest.approx(result.metrics.total_return)
    assert stored["max_drawdown"] == pytest.approx(result.metrics.max_drawdown)
    assert stored["profit_factor"] == pytest.approx(result.metrics.profit_factor)  # 0.10/0.05 = 2.0
    assert stored["sharpe_ratio"] == pytest.approx(result.metrics.sharpe_ratio)


def test_reloaded_trades_match(db_session):
    repo = BacktestRepository(db_session)
    bid = repo.save(symbol="ACME", signal="manual", result=_manual_result())
    trades = repo.get(bid).trades
    assert len(trades) == 2
    assert {t.reason for t in trades} == {"TARGET", "STOP"}
    assert trades[0].return_pct == pytest.approx(0.10)


def test_list_filters_by_symbol(db_session):
    repo = BacktestRepository(db_session)
    repo.save(symbol="AAA", signal="manual", result=_manual_result())
    repo.save(symbol="BBB", signal="manual", result=_manual_result())
    assert {r.symbol for r in repo.list()} == {"AAA", "BBB"}
    assert [r.symbol for r in repo.list(symbol="AAA")] == ["AAA"]


def test_reproducibility_on_record(db_session, tmp_path):
    store = BarStore(tmp_path / "col")
    store.write_bars("ACME", _ohlc([10, 10, 10, 12, 14, 12, 10, 9]))

    def fn(bars):
        return sma_crossover_signals(bars, fast=2, slow=3)

    result = run_symbol_backtest(store, "ACME", fn)
    repo = BacktestRepository(db_session)
    bid = repo.save(symbol="ACME", signal="sma_crossover_2_3", result=result)
    stored = repo.get_metrics(bid)

    # Re-run from scratch: stored metrics must equal the freshly computed ones.
    rerun = run_symbol_backtest(store, "ACME", fn)
    assert stored["total_return"] == pytest.approx(rerun.metrics.total_return)
    assert stored["max_drawdown"] == pytest.approx(rerun.metrics.max_drawdown)
    assert stored["sharpe_ratio"] == pytest.approx(rerun.metrics.sharpe_ratio)
