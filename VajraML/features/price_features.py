"""
Phase 1 — Price-derived features.

All rolling operations use groupby so they never bleed across stock
boundaries, even when the full universe DataFrame is passed in one shot.

Input DataFrame must contain:
  symbol_id, trading_date, open, high, low, close, adj_close, volume
and must be sorted by (symbol_id, trading_date).
"""

import numpy as np
import pandas as pd

from VajraML.config import HIGH_LOOKBACK, ROLLING_VOL_WINDOW, VOLUME_AVG_WINDOW


def compute_price_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # ── Log returns ───────────────────────────────────────────────────────────
    # Use adj_close so dividends / bonuses don't create spurious return spikes.
    g = df.groupby("symbol_id")["adj_close"]

    df["log_ret_1d"]  = g.transform(lambda x: np.log(x / x.shift(1)))
    df["log_ret_5d"]  = g.transform(lambda x: np.log(x / x.shift(5)))
    df["log_ret_10d"] = g.transform(lambda x: np.log(x / x.shift(10)))
    df["log_ret_20d"] = g.transform(lambda x: np.log(x / x.shift(20)))

    # ── Realised volatility ───────────────────────────────────────────────────
    # Annualised 20-day vol of daily log returns.
    # Needed as a feature (volatility regime) AND as the denominator in the
    # vol-adjusted target — computed independently in target.py to maintain isolation.
    df["rolling_vol_20d"] = (
        df.groupby("symbol_id")["log_ret_1d"]
          .transform(lambda x: x.rolling(ROLLING_VOL_WINDOW, min_periods=10).std() * np.sqrt(252))
    )

    # ── Volume ratio ──────────────────────────────────────────────────────────
    # Today's volume relative to its own 20-day average.
    # Normalises cross-stock and time differences; values > 1 signal unusual activity.
    avg_vol = df.groupby("symbol_id")["volume"].transform(
        lambda x: x.rolling(VOLUME_AVG_WINDOW, min_periods=5).mean()
    )
    df["volume_ratio_20d"] = df["volume"] / avg_vol.replace(0, np.nan)

    # ── Candle structure ──────────────────────────────────────────────────────
    h_l = (df["high"] - df["low"]).replace(0, np.nan)

    df["range_pct"]    = h_l / df["close"]
    df["body_ratio"]   = (df["close"] - df["open"]) / h_l
    df["upper_shadow"] = (df["high"] - df[["close", "open"]].max(axis=1)) / h_l
    df["lower_shadow"] = (df[["close", "open"]].min(axis=1) - df["low"]) / h_l

    # ── 52-week high proximity ────────────────────────────────────────────────
    # Proximity to the rolling 252-day high: 1.0 = at all-time high, <1 = below.
    # This replaces sma_200 (which has 28% nulls) as the long-term trend signal.
    rolling_high = df.groupby("symbol_id")["high"].transform(
        lambda x: x.rolling(HIGH_LOOKBACK, min_periods=100).max()
    )
    df["high_52w_proximity"] = df["close"] / rolling_high.replace(0, np.nan)

    return df
