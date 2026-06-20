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

    # ── MA / Price crossover recency features ─────────────────────────────────
    # Each _bull_xover_days call: O(n) vectorised, no Python loops.
    # Only bull direction kept for price-vs-MA (bear = existing close_vs_sma20 < 0).
    df = _bull_xover_days(df, "symbol_id", "close", "sma_20",
                          "days_since_price_sma20_bull", XOVER_CAP_DAYS)
    df = _bull_xover_days(df, "symbol_id", "close", "sma_50",
                          "days_since_price_sma50_bull", XOVER_CAP_DAYS)
    df = _bull_xover_days(df, "symbol_id", "close", "ema_20",
                          "days_since_price_ema20_bull", XOVER_CAP_DAYS)

    # EMA ribbon and MA golden/death cross — both directions useful
    df = _xover_days(df, "symbol_id", "ema_9", "ema_20",
                     "days_since_ema9_ema20_bull", "days_since_ema9_ema20_bear", XOVER_CAP_DAYS)
    df = _bull_xover_days(df, "symbol_id", "sma_20", "sma_50",
                          "days_since_sma20_sma50_bull", XOVER_CAP_DAYS)
    df = _xover_days(df, "symbol_id", "macd_line", "macd_signal",
                     "days_since_macd_bull", "days_since_macd_bear", XOVER_CAP_DAYS)

    # CMF vs zero — add zero column temporarily for generic helper
    df["_zero"] = 0.0
    df = _xover_days(df, "symbol_id", "cmf_20", "_zero",
                     "days_since_cmf_bull", "days_since_cmf_bear", XOVER_CAP_DAYS)
    df.drop(columns=["_zero"], inplace=True)

    # ── Continuous crossover distance / momentum ──────────────────────────────
    # EMA9-EMA20 spread as % of close: positive = ribbon bullish, negative = bearish
    df["ema9_ema20_spread"] = (
        (df["ema_9"] - df["ema_20"]) / df["close"].replace(0, np.nan) * 100
    )

    # MACD histogram 3-day slope: momentum-of-momentum, early reversal signal
    df["macd_histogram_slope"] = df.groupby("symbol_id")["macd_histogram"].transform(
        lambda x: (x - x.shift(3)) / 3
    )

    # Is MACD line above zero? Separates trending-up vs trending-down market context
    df["macd_above_zero"] = (df["macd_line"] > 0).astype(float)

    # CMF 5-day momentum: is money flow accelerating or decelerating?
    df["cmf_slope_5d"] = df.groupby("symbol_id")["cmf_20"].transform(
        lambda x: x - x.shift(5)
    )

    return df


def _bull_xover_days(df: pd.DataFrame, symbol_col: str, fast_col: str, slow_col: str,
                     out_name: str, cap: int) -> pd.DataFrame:
    """Add a single bull days-since-crossover column (fast crossed above slow)."""
    df["_xa"] = (df[fast_col] > df[slow_col]).astype(float)
    prev = df.groupby(symbol_col)["_xa"].shift(1)
    df["_xb"] = ((df["_xa"] == 1) & (prev == 0)).astype(float)
    df[out_name] = df.groupby(symbol_col)["_xb"].transform(
        lambda s: _days_since_event(s, cap=cap)
    )
    df.drop(columns=["_xa", "_xb"], inplace=True)
    return df


def _xover_days(df: pd.DataFrame, symbol_col: str, fast_col: str, slow_col: str,
                bull_name: str, bear_name: str, cap: int) -> pd.DataFrame:
    """Add bull and bear days-since-crossover columns (fast crosses above/below slow)."""
    df["_xa"] = (df[fast_col] > df[slow_col]).astype(float)
    prev = df.groupby(symbol_col)["_xa"].shift(1)
    df["_xb"] = ((df["_xa"] == 1) & (prev == 0)).astype(float)
    df["_xc"] = ((df["_xa"] == 0) & (prev == 1)).astype(float)
    df[bull_name] = df.groupby(symbol_col)["_xb"].transform(
        lambda s: _days_since_event(s, cap=cap)
    )
    df[bear_name] = df.groupby(symbol_col)["_xc"].transform(
        lambda s: _days_since_event(s, cap=cap)
    )
    df.drop(columns=["_xa", "_xb", "_xc"], inplace=True)
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
