"""
Phase 2 — Indicator ratio transforms and derived features.

Every raw indicator is converted to a price-independent, cross-stock-comparable
form.  Raw MA / band values are meaningless across stocks at different price
levels; their distance from the current price (as a %) is what carries signal.

Input DataFrame must already contain Phase 1 price features plus all raw
indicator columns from daily_indicators.
"""

import numpy as np
import pandas as pd

from VajraML.config import OBV_CHANGE_WINDOW, OBV_MA_WINDOW, XOVER_CAP_DAYS


def compute_indicator_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # ── EMA distance from close (% format) ───────────────────────────────────
    for col, out in [("ema_9", "close_vs_ema9"),
                     ("ema_20", "close_vs_ema20"),
                     ("ema_21", "close_vs_ema21")]:
        df[out] = (df["close"] - df[col]) / df["close"]

    # ── SMA distance from close ───────────────────────────────────────────────
    for col, out in [("sma_20", "close_vs_sma20"),
                     ("sma_50", "close_vs_sma50")]:
        df[out] = (df["close"] - df[col]) / df["close"]

    # ── Bollinger Band features ───────────────────────────────────────────────
    bb_range = (df["bb_upper"] - df["bb_lower"]).replace(0, np.nan)
    # %B: 0 = at lower band, 0.5 = at midline, 1 = at upper band
    df["bb_pct_b"]     = (df["close"] - df["bb_lower"]) / bb_range
    # Bandwidth: large = volatile/expanding, small = squeeze
    df["bb_bandwidth"] = bb_range / df["bb_middle"].replace(0, np.nan)

    # ── Supertrend ────────────────────────────────────────────────────────────
    # Distance from dynamic support/resistance as a % of price
    df["close_vs_supertrend"] = (df["close"] - df["supertrend"]) / df["close"]
    # Direction encoded numerically so LGBM can use it as a continuous feature
    df["supertrend_dir_enc"]  = df["supertrend_dir"].map({"UP": 1.0, "DOWN": -1.0})

    # ── ATR % ─────────────────────────────────────────────────────────────────
    # Raw ATR is in price units; divide by close to make it comparable cross-stock
    df["atr_pct"] = (df["atr_14"] / df["close"].replace(0, np.nan)) * 100

    # ── Directional Index net pressure ───────────────────────────────────────
    # Positive = bulls stronger, negative = bears stronger
    df["di_diff"] = df["plus_di"] - df["minus_di"]

    # ── Stochastic crossover strength ─────────────────────────────────────────
    df["stoch_kd_diff"]    = df["stoch_k"] - df["stoch_d"]
    df["stochrsi_kd_diff"] = df["stochrsi_k"] - df["stochrsi_d"]

    # ── OBV — fix non-stationarity ────────────────────────────────────────────
    # Raw OBV is a cumulative sum from an arbitrary start date: non-stationary,
    # non-comparable across stocks or time windows.  Use rate-of-change and
    # its deviation from its own MA instead.
    df["obv_ret_5d"] = df.groupby("symbol_id")["obv"].transform(
        lambda x: (x - x.shift(OBV_CHANGE_WINDOW))
                  / x.shift(OBV_CHANGE_WINDOW).abs().replace(0, np.nan)
    )
    obv_ma = df.groupby("symbol_id")["obv"].transform(
        lambda x: x.rolling(OBV_MA_WINDOW, min_periods=5).mean()
    )
    df["obv_vs_ma20"] = df["obv"] / obv_ma.replace(0, np.nan)

    # ── Days since StochRSI crossover ─────────────────────────────────────────
    # The raw boolean xover flag fires only on the day of the cross; recency
    # (how many days ago) is the more useful model feature.
    df["days_since_bull_xover"] = df.groupby("symbol_id")[
        "stochrsi_bullish_xover"
    ].transform(lambda s: _days_since_event(s, cap=XOVER_CAP_DAYS))

    df["days_since_bear_xover"] = df.groupby("symbol_id")[
        "stochrsi_bearish_xover"
    ].transform(lambda s: _days_since_event(s, cap=XOVER_CAP_DAYS))

    return df


def _days_since_event(s: pd.Series, cap: int = 20) -> pd.Series:
    """
    Vectorised: trading days since the last True in a boolean Series, capped.

    Uses the forward-fill-of-event-index trick — O(n), no Python loops.
    """
    s = s.fillna(0).astype(bool)
    pos = np.arange(len(s), dtype=float)

    # For each position, record the position index if it's an event, else NaN
    event_pos = pd.Series(np.where(s, pos, np.nan), index=s.index)
    last_event = event_pos.ffill()

    days = pd.Series(pos, index=s.index) - last_event
    days = days.clip(upper=cap)
    days[last_event.isna()] = float(cap)   # no event seen yet -> cap
    return days
