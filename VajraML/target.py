"""
Forward return target computation.

ISOLATION RULE: This module has NO dependency on any feature module.
The target DataFrame is computed and stored separately from the feature
matrix.  It is only joined inside pipeline.py at the very last step —
and only by (symbol_id, trading_date), never by value.

Using adj_close (not close) is critical: dividends and bonus issues on NSE
create artificial price drops that would otherwise appear as strong bearish
signals in the raw close price.
"""

import numpy as np
import pandas as pd

from VajraML.config import FORWARD_DAYS, RETURN_THRESHOLDS


def compute_targets(
    prices: pd.DataFrame,
    forward_days: int = FORWARD_DAYS,
) -> pd.DataFrame:
    """
    Compute forward return targets from adjusted close prices.

    Input must contain: symbol_id, trading_date, adj_close.
    Must already be sorted by (symbol_id, trading_date).

    Adds columns:
      fwd_ret_5d       — raw 5-day forward % return (used for trading evaluation)
      fwd_ret_vol_adj  — volatility-adjusted forward return (primary training target)
      return_label     — 5-class human-readable label derived from fwd_ret_5d
    """
    df = prices[["symbol_id", "trading_date", "adj_close"]].copy()
    df = df.sort_values(["symbol_id", "trading_date"])

    # Raw forward return using adj_close to account for dividends / bonuses
    fwd = df.groupby("symbol_id")["adj_close"].shift(-forward_days)
    df["fwd_ret_5d"] = (fwd / df["adj_close"]) - 1

    # 20-day rolling annualised volatility for vol-adjustment
    log_ret = df.groupby("symbol_id")["adj_close"].transform(
        lambda x: np.log(x / x.shift(1)).rolling(20, min_periods=10).std() * np.sqrt(252)
    )

    # Vol-adjusted target — the forward Sharpe ratio.
    # This normalises return expectations across high-vol and low-vol stocks,
    # making predictions comparable cross-sectionally.
    df["fwd_ret_vol_adj"] = df["fwd_ret_5d"] / log_ret.replace(0, np.nan)

    # 5-class label for human-readable output (not used in model training)
    df["return_label"] = df["fwd_ret_5d"].apply(_label)

    return df.drop(columns=["adj_close"])


def _label(ret: float) -> str:
    if pd.isna(ret):
        return "Unknown"
    for name, (lo, hi) in RETURN_THRESHOLDS.items():
        if lo <= ret < hi:
            return name
    return "Very Bullish"
