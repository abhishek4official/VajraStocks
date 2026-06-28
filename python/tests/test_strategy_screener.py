"""Materializer tests — load-once/bulk path, orphan purge, determinism."""

import datetime as dt

import numpy as np
import pandas as pd
from sqlalchemy import func, select

from stocks.db.models import DailyPrice, StrategySignal, Symbol
from stocks.services.strategies.registry import list_strategies
from stocks.services.strategy_screener import StrategyScreenerService


def _seed_prices(db, sym, n=420, start=40.0, end=180.0, seed=1):
    rng = np.random.RandomState(seed)
    px = np.linspace(start, end, n) + rng.normal(0, 0.6, n)
    dates = pd.bdate_range("2023-01-02", periods=n)
    for d, p in zip(dates, px):
        db.add(DailyPrice(
            symbol_id=sym.id, trading_date=d.date(), open=float(p), high=float(p * 1.01),
            low=float(p * 0.99), close=float(p), adj_close=float(p), volume=1_000_000, granularity="1d",
        ))


def _seed_universe(db):
    nsei = Symbol(symbol="^NSEI", company_name="NIFTY 50", isin="IDX_NSEI", series="IDX", is_active=True)
    acme = Symbol(symbol="ACME.NS", company_name="Acme Ltd", isin="INE00ACME", series="EQ", is_active=True)
    beta = Symbol(symbol="BETA.NS", company_name="Beta Ltd", isin="INE00BETA", series="EQ", is_active=True)
    db.add_all([nsei, acme, beta])
    db.commit()
    _seed_prices(db, nsei, start=18000, end=21000, seed=2)
    _seed_prices(db, acme, start=40, end=200, seed=3)
    _seed_prices(db, beta, start=50, end=120, seed=4)
    db.commit()
    return nsei, acme, beta


def test_refresh_all_strategies_writes_every_strategy(db_session, test_config):
    _seed_universe(db_session)
    svc = StrategyScreenerService(test_config, db_session)
    counts = svc.refresh_all_strategies(force_market_ok=True)

    registered = {a.id for a in list_strategies()}
    assert set(counts) == registered
    # Each strategy should have written a row for both active equities (not the index).
    for sid in registered:
        n = db_session.scalar(
            select(func.count()).select_from(StrategySignal).where(StrategySignal.strategy_id == sid)
        )
        assert n == 2, f"{sid} wrote {n} rows"
    # No index rows materialized.
    assert db_session.scalar(select(func.count()).select_from(StrategySignal).where(StrategySignal.symbol == "^NSEI")) == 0


def test_orphan_strategy_rows_are_purged(db_session, test_config):
    nsei, acme, beta = _seed_universe(db_session)
    # Seed a stale row for a retired strategy.
    db_session.add(StrategySignal(
        symbol_id=acme.id, symbol="ACME.NS", company_name="Acme Ltd", strategy_id="pre_breakout_v2",
        as_of=dt.date(2026, 6, 5), signal="BUY", score=80.0, last_close=100.0, updated_at=dt.datetime.utcnow(),
    ))
    db_session.commit()
    StrategyScreenerService(test_config, db_session).refresh_all_strategies(force_market_ok=True)
    assert db_session.scalar(
        select(func.count()).select_from(StrategySignal).where(StrategySignal.strategy_id == "pre_breakout_v2")
    ) == 0


def test_determinism_same_counts_on_rerun(db_session, test_config):
    _seed_universe(db_session)
    svc = StrategyScreenerService(test_config, db_session)
    a = svc.refresh_all_strategies(force_market_ok=True)
    b = svc.refresh_all_strategies(force_market_ok=True)
    assert a == b


def test_single_strategy_refresh(db_session, test_config):
    _seed_universe(db_session)
    svc = StrategyScreenerService(test_config, db_session)
    n = svc.refresh_all_signals("minervini", force_market_ok=True)
    assert n == 2
    rows = db_session.scalars(select(StrategySignal).where(StrategySignal.strategy_id == "minervini")).all()
    assert all(r.score is not None for r in rows)
