"""Tests for query-time corporate-action back-adjustment (V2 hybrid-DB data plane).

Design contract (see Doc/VajraStocks_V2.0_PRD_BRD_Architecture.md §18):
- Raw/unadjusted OHLCV bars are the immutable system of record (Parquet).
- Adjustments are applied AT QUERY TIME from corporate-action factors.
- Back-adjustment convention: the most-recent bars stay at their raw price; only
  bars STRICTLY BEFORE a split's ex-date are divided by the split ratio, so the
  adjusted series is continuous and the latest adjusted price == latest raw price.
"""

import datetime as dt

import pandas as pd
import pytest

from stocks.data.adjustments import (
    apply_adjustments,
    apply_split_adjustments,
    split_adjustment_factors,
)

D = dt.date


def _bars() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"trading_date": D(2024, 6, 7),  "open": 198, "high": 202, "low": 196, "close": 200, "adj_close": 200, "volume": 1000},
            {"trading_date": D(2024, 6, 10), "open": 100, "high": 103, "low": 99,  "close": 100, "adj_close": 100, "volume": 2200},
            {"trading_date": D(2024, 6, 11), "open": 100, "high": 104, "low": 100, "close": 101, "adj_close": 101, "volume": 1500},
        ]
    )


def test_no_actions_returns_unchanged():
    bars = _bars()
    out = apply_split_adjustments(bars, actions=[])
    pd.testing.assert_frame_equal(out.reset_index(drop=True), bars.reset_index(drop=True))


def test_factors_product_of_splits_after_date():
    actions = [{"action_date": D(2024, 6, 10), "action_type": "SPLIT", "value": 2.0}]
    factors = split_adjustment_factors([D(2024, 6, 7), D(2024, 6, 10), D(2024, 6, 11)], actions)
    assert factors[D(2024, 6, 7)] == 2.0   # split is after this date → divide by 2
    assert factors[D(2024, 6, 10)] == 1.0  # ex-date itself: action_date NOT strictly after → 1
    assert factors[D(2024, 6, 11)] == 1.0  # after the split → 1


def test_single_2for1_split_backadjusts_prior_bars_only():
    actions = [{"action_date": D(2024, 6, 10), "action_type": "SPLIT", "value": 2.0}]
    out = apply_split_adjustments(_bars(), actions).set_index("trading_date")

    # Pre-split bar: prices halved, volume doubled
    assert out.loc[D(2024, 6, 7), "close"] == 100
    assert out.loc[D(2024, 6, 7), "open"] == 99
    assert out.loc[D(2024, 6, 7), "high"] == 101
    assert out.loc[D(2024, 6, 7), "low"] == 98
    assert out.loc[D(2024, 6, 7), "volume"] == 2000

    # Ex-date and later bars: untouched
    assert out.loc[D(2024, 6, 10), "close"] == 100
    assert out.loc[D(2024, 6, 10), "volume"] == 2200
    assert out.loc[D(2024, 6, 11), "close"] == 101


def test_multiple_splits_compound():
    # 2:1 on Jun 10 and 3:1 on Jun 11 → a bar before both is divided by 6
    actions = [
        {"action_date": D(2024, 6, 10), "action_type": "SPLIT", "value": 2.0},
        {"action_date": D(2024, 6, 11), "action_type": "SPLIT", "value": 3.0},
    ]
    factors = split_adjustment_factors([D(2024, 6, 7)], actions)
    assert factors[D(2024, 6, 7)] == 6.0


def test_dividend_actions_ignored_by_split_adjustment():
    actions = [{"action_date": D(2024, 6, 10), "action_type": "DIVIDEND", "value": 5.0}]
    out = apply_split_adjustments(_bars(), actions)
    pd.testing.assert_frame_equal(out.reset_index(drop=True), _bars().reset_index(drop=True))


def test_string_dates_accepted():
    # Actions/bars may arrive with ISO string dates from the DB layer.
    bars = _bars()
    bars["trading_date"] = bars["trading_date"].astype(str)
    actions = [{"action_date": "2024-06-10", "action_type": "SPLIT", "value": 2.0}]
    out = apply_split_adjustments(bars, actions)
    out = out.set_index(pd.to_datetime(out["trading_date"]).dt.date)
    assert out.loc[D(2024, 6, 7), "close"] == 100


# ── dividend back-adjustment ────────────────────────────────────────────────
# Convention: on ex-date E with dividend Div and prior close C_prev (close of the
# last bar strictly before E), bars with date < E are multiplied by (1 - Div/C_prev);
# bars on/after E are untouched; volume is NOT changed by a dividend.


def test_dividend_backadjusts_prior_bars():
    actions = [{"action_date": D(2024, 6, 10), "action_type": "DIVIDEND", "value": 5.0}]
    out = apply_adjustments(_bars(), actions).set_index("trading_date")
    # prior close = 200 (2024-06-07 close) → factor = 1 - 5/200 = 0.975
    assert out.loc[D(2024, 6, 7), "close"] == pytest.approx(195.0)
    assert out.loc[D(2024, 6, 7), "volume"] == 1000  # volume unchanged by dividend
    assert out.loc[D(2024, 6, 10), "close"] == 100   # ex-date untouched
    assert out.loc[D(2024, 6, 11), "close"] == 101


def test_dividend_with_no_prior_bar_is_skipped():
    # Ex-date equals the first bar's date → no prior close to compute a factor → skip.
    actions = [{"action_date": D(2024, 6, 7), "action_type": "DIVIDEND", "value": 5.0}]
    out = apply_adjustments(_bars(), actions)
    pd.testing.assert_frame_equal(out.reset_index(drop=True), _bars().reset_index(drop=True))


def test_split_and_dividend_compound():
    # Split 2:1 and a 5.00 dividend, both ex 2024-06-10.
    # Dividend prior close uses the RAW prior close (200) → div factor 0.975.
    # Split factor halves. Pre-event bar: 200 * 0.5 * 0.975 = 97.5
    actions = [
        {"action_date": D(2024, 6, 10), "action_type": "SPLIT", "value": 2.0},
        {"action_date": D(2024, 6, 10), "action_type": "DIVIDEND", "value": 5.0},
    ]
    out = apply_adjustments(_bars(), actions).set_index("trading_date")
    assert out.loc[D(2024, 6, 7), "close"] == pytest.approx(97.5)
    assert out.loc[D(2024, 6, 7), "volume"] == 2000  # doubled by split, unaffected by dividend


def test_apply_split_adjustments_ignores_dividends():
    actions = [{"action_date": D(2024, 6, 10), "action_type": "DIVIDEND", "value": 5.0}]
    out = apply_split_adjustments(_bars(), actions)
    pd.testing.assert_frame_equal(out.reset_index(drop=True), _bars().reset_index(drop=True))
