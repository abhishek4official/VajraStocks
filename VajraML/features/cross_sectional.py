"""
Phase 3 — Cross-sectional percentile ranks + universe breadth.

For each trading date, every stock's indicator is ranked against the
full 700-stock universe on that same day (0 = worst, 1 = best).

Why this matters: RSI of 65 in isolation is ambiguous.  RSI rank of 0.85
means the stock is in the top 15% of the universe by RSI — a much stronger
and less noisy signal because it removes the common-factor component
(e.g. all stocks overbought during a broad rally).

Percentile rank is bounded [0, 1] by construction: no normalisation needed.

Universe breadth features: same value for all stocks on a given date,
providing a market-wide context signal.
"""

import pandas as pd

FEATURES_TO_RANK = [
    "rsi_14",
    "macd_histogram",
    "volume_ratio_20d",
    "log_ret_5d",
    "log_ret_20d",
    "cmf_20",
    "atr_pct",
]


def compute_cross_sectional_ranks(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add {feature}_rank columns (0-1 percentile) computed within each date,
    plus universe breadth indicators (% of stocks above their moving averages).
    """
    df = df.copy()

    # Per-stock percentile ranks within the universe on each date
    for feat in FEATURES_TO_RANK:
        if feat not in df.columns:
            continue
        df[f"{feat}_rank"] = df.groupby("trading_date")[feat].transform(
            lambda x: x.rank(pct=True, na_option="bottom")
        )

    # Universe breadth: fraction of stocks above their moving averages.
    # Same value for every stock on a given date — a market-wide regime signal.
    if "close_vs_sma20" in df.columns:
        df["universe_breadth_20d"] = df.groupby("trading_date")["close_vs_sma20"].transform(
            lambda x: (x > 0).mean()
        )

    if "close_vs_sma50" in df.columns:
        df["universe_breadth_50d"] = df.groupby("trading_date")["close_vs_sma50"].transform(
            lambda x: (x > 0).mean()
        )

    return df
