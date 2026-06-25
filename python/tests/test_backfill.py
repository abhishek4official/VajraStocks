"""Tests for the SQLite -> Parquet backfill and the corporate-action adapter.

Moves the historical price series from the transactional store (DailyPrice) into the
columnar BarStore, and exposes CorporateAction rows in the shape read_bars() expects
for query-time adjustment. See Doc/VajraStocks_V2.0_PRD_BRD_Architecture.md §18, §27.
"""

import datetime as dt

import pytest

from stocks.config import Config
from stocks.data.backfill import (
    backfill_all,
    backfill_symbol,
    load_actions,
    sync_columnar_store,
)
from stocks.data.bar_store import BarStore
from stocks.db.models import CorporateAction, DailyPrice, Symbol

D = dt.date


@pytest.fixture
def store(tmp_path):
    return BarStore(tmp_path / "columnar")


def _add_symbol(session, symbol: str, suffix: str) -> Symbol:
    sym = Symbol(
        symbol=symbol,
        company_name=f"{symbol} Ltd",
        isin=f"INE{suffix}01015",
        series="EQ",
        is_active=True,
    )
    session.add(sym)
    session.flush()  # assigns sym.id
    return sym


def _add_price(session, symbol_id: int, d: dt.date, close: float, volume: int = 1000):
    session.add(
        DailyPrice(
            symbol_id=symbol_id, trading_date=d,
            open=close, high=close, low=close, close=close, adj_close=close,
            volume=volume, granularity="1d", data_source="TEST",
        )
    )


def test_backfill_empty_symbol_returns_zero(db_session, store):
    sym = _add_symbol(db_session, "EMPTY", "999")
    assert backfill_symbol(db_session, store, sym.id, sym.symbol) == 0


def test_backfill_symbol_writes_bars(db_session, store):
    sym = _add_symbol(db_session, "RELIANCE", "002")
    _add_price(db_session, sym.id, D(2023, 1, 2), 104.0, 1000)
    _add_price(db_session, sym.id, D(2023, 1, 3), 107.0, 1200)
    db_session.flush()

    n = backfill_symbol(db_session, store, sym.id, sym.symbol)
    assert n == 2

    out = store.read_bars("RELIANCE").set_index("trading_date")
    assert out.loc[D(2023, 1, 3), "close"] == 107.0
    assert out.loc[D(2023, 1, 2), "volume"] == 1000


def test_backfill_all_returns_counts(db_session, store):
    a = _add_symbol(db_session, "AAA", "003")
    b = _add_symbol(db_session, "BBB", "004")
    _add_price(db_session, a.id, D(2023, 1, 2), 10.0)
    _add_price(db_session, b.id, D(2023, 1, 2), 20.0)
    _add_price(db_session, b.id, D(2023, 1, 3), 21.0)
    db_session.flush()

    result = backfill_all(db_session, store)
    assert result == {"AAA": 1, "BBB": 2}


def test_load_actions_returns_dicts(db_session):
    sym = _add_symbol(db_session, "ACME", "005")
    db_session.add(CorporateAction(symbol_id=sym.id, action_date=D(2024, 6, 10), action_type="SPLIT", value=2.0))
    db_session.add(CorporateAction(symbol_id=sym.id, action_date=D(2024, 3, 1), action_type="DIVIDEND", value=5.0))
    db_session.flush()

    actions = load_actions(db_session, sym.id)
    assert {a["action_type"] for a in actions} == {"SPLIT", "DIVIDEND"}
    split = next(a for a in actions if a["action_type"] == "SPLIT")
    assert split["action_date"] == D(2024, 6, 10)
    assert split["value"] == 2.0
    assert isinstance(split["value"], float)


def test_backfill_then_read_adjusted(db_session, store):
    sym = _add_symbol(db_session, "ACME", "006")
    _add_price(db_session, sym.id, D(2024, 6, 7), 200.0, 1000)
    _add_price(db_session, sym.id, D(2024, 6, 11), 101.0, 1500)
    db_session.add(CorporateAction(symbol_id=sym.id, action_date=D(2024, 6, 10), action_type="SPLIT", value=2.0))
    db_session.flush()

    backfill_symbol(db_session, store, sym.id, sym.symbol)
    actions = load_actions(db_session, sym.id)
    out = store.read_bars("ACME", adjusted=True, actions=actions).set_index("trading_date")
    assert out.loc[D(2024, 6, 7), "close"] == 100.0   # back-adjusted for the 2:1 split
    assert out.loc[D(2024, 6, 7), "volume"] == 2000


def test_sync_columnar_store_mirrors_all(db_manager, tmp_path):
    # Seed and COMMIT so the job's own fresh session can see the data.
    session = db_manager.get_session()
    try:
        a = _add_symbol(session, "AAA", "007")
        b = _add_symbol(session, "BBB", "008")
        _add_price(session, a.id, D(2023, 1, 2), 10.0)
        _add_price(session, b.id, D(2023, 1, 2), 20.0)
        _add_price(session, b.id, D(2023, 1, 3), 21.0)
        session.commit()
    finally:
        session.close()

    cfg = Config()
    cfg.storage.columnar_data_dir = str(tmp_path / "col")

    result = sync_columnar_store(db_manager, cfg)
    assert result == {"AAA": 1, "BBB": 2}

    store = BarStore.from_config(cfg)
    assert store.read_bars("BBB").iloc[-1]["close"] == 21.0
