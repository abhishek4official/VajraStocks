"""Tests for the DuckDB + partitioned-Parquet bar store (V2 hybrid-DB data plane).

Contract (see Doc/VajraStocks_V2.0_PRD_BRD_Architecture.md §3A, §17, §18):
- Bars are persisted as Parquet partitioned by symbol and year (Hive layout) so a
  query for one symbol/year prunes to just those files.
- write_bars() upserts by trading_date (re-writing a date replaces it; new dates append).
- read_bars() returns rows sorted by date, optionally back-adjusted at query time.
"""

import datetime as dt

import pandas as pd
import pytest

from stocks.data.bar_store import BarStore

D = dt.date


@pytest.fixture
def store(tmp_path):
    return BarStore(tmp_path / "columnar")


def _bars(rows):
    return pd.DataFrame(
        [
            {
                "trading_date": d,
                "open": o, "high": h, "low": low, "close": c,
                "adj_close": c, "volume": v,
            }
            for (d, o, h, low, c, v) in rows
        ]
    )


def test_read_missing_symbol_returns_empty(store):
    out = store.read_bars("NOPE")
    assert out.empty


def test_write_then_read_roundtrip(store):
    bars = _bars([
        (D(2023, 1, 2), 100, 105, 99, 104, 1000),
        (D(2023, 1, 3), 104, 108, 103, 107, 1200),
    ])
    n = store.write_bars("RELIANCE", bars)
    assert n == 2

    out = store.read_bars("RELIANCE").set_index("trading_date")
    assert list(out.index) == [D(2023, 1, 2), D(2023, 1, 3)]
    assert out.loc[D(2023, 1, 3), "close"] == 107
    assert out.loc[D(2023, 1, 2), "volume"] == 1000


def test_read_date_range_filter(store):
    store.write_bars("ACME", _bars([
        (D(2023, 1, 2), 10, 11, 9, 10, 100),
        (D(2023, 2, 1), 12, 13, 11, 12, 100),
        (D(2023, 3, 1), 14, 15, 13, 14, 100),
    ]))
    out = store.read_bars("ACME", start=D(2023, 2, 1), end=D(2023, 2, 28))
    assert list(out["trading_date"]) == [D(2023, 2, 1)]


def test_upsert_overwrites_same_date(store):
    store.write_bars("ACME", _bars([(D(2023, 1, 2), 10, 11, 9, 10, 100)]))
    # Re-write the same date with a finalized close — must replace, not duplicate.
    store.write_bars("ACME", _bars([(D(2023, 1, 2), 10, 12, 9, 11, 150)]))
    out = store.read_bars("ACME")
    assert len(out) == 1
    assert out.iloc[0]["close"] == 11
    assert out.iloc[0]["volume"] == 150


def test_append_new_dates_preserves_existing(store):
    store.write_bars("ACME", _bars([(D(2023, 1, 2), 10, 11, 9, 10, 100)]))
    store.write_bars("ACME", _bars([(D(2023, 1, 3), 10, 12, 9, 11, 150)]))
    out = store.read_bars("ACME")
    assert list(out["trading_date"]) == [D(2023, 1, 2), D(2023, 1, 3)]


def test_partitioned_by_symbol_and_year(store, tmp_path):
    store.write_bars("ACME", _bars([
        (D(2022, 12, 30), 10, 11, 9, 10, 100),
        (D(2023, 1, 3), 12, 13, 11, 12, 100),
    ]))
    root = tmp_path / "columnar"
    paths = {p.as_posix() for p in root.rglob("*.parquet")}
    assert any("symbol=ACME" in p and "year=2022" in p for p in paths)
    assert any("symbol=ACME" in p and "year=2023" in p for p in paths)


def test_symbols_are_isolated(store):
    store.write_bars("AAA", _bars([(D(2023, 1, 2), 10, 11, 9, 10, 100)]))
    store.write_bars("BBB", _bars([(D(2023, 1, 2), 20, 21, 19, 20, 200)]))
    assert store.read_bars("AAA").iloc[0]["close"] == 10
    assert store.read_bars("BBB").iloc[0]["close"] == 20
    assert sorted(store.list_symbols()) == ["AAA", "BBB"]


def test_read_adjusted_applies_split(store):
    store.write_bars("ACME", _bars([
        (D(2024, 6, 7), 198, 202, 196, 200, 1000),
        (D(2024, 6, 11), 100, 104, 100, 101, 1500),
    ]))
    actions = [{"action_date": D(2024, 6, 10), "action_type": "SPLIT", "value": 2.0}]
    out = store.read_bars("ACME", adjusted=True, actions=actions).set_index("trading_date")
    assert out.loc[D(2024, 6, 7), "close"] == 100   # halved
    assert out.loc[D(2024, 6, 7), "volume"] == 2000  # doubled
    assert out.loc[D(2024, 6, 11), "close"] == 101   # after split, untouched
