"""
Triple-barrier label computation.

ISOLATION RULE: same as VajraML target.py — no dependency on any feature
module.  Labels are computed from raw OHLCV + ATR and joined by key only.

Triple-barrier logic
────────────────────
For each (symbol, date) entry at close price C with ATR = A:

  Take-profit barrier  TP = C + TP_ATR_MULT * A
  Stop-loss barrier    SL = C - SL_ATR_MULT * A
  Time barrier             = BARRIER_HORIZON trading days

Scan forward day-by-day using daily High and Low:
  Day d=1..HORIZON:
    - If High[d] >= TP  AND this is the first touch → record tp_day = d
    - If Low[d]  <= SL  AND this is the first touch → record sl_day = d

  Final label:
    +1  (TB_CLASS_TP)   if tp_day < sl_day   (TP hit first)
    -1  (TB_CLASS_SL)   if sl_day < tp_day   (SL hit first)
     0  (TB_CLASS_TIME) otherwise             (time barrier or same-day tie)

Encoding:
  tb_label     ∈ {-1, 0, +1}  (human-readable)
  tb_label_enc ∈ {0, 1, 2}    (0-indexed for LightGBM)  →  tb_label + 1

NSE note: circuit-breaker days (5%/10%/20% limits) appear naturally in
daily High/Low data — no special handling required.

Implementation: fully vectorised — iterates over BARRIER_HORIZON (5)
passes through the DataFrame with grouped shifts, no Python row loops.
"""

import numpy as np
import pandas as pd

from VajraML2.config import BARRIER_HORIZON, SL_ATR_MULT, TP_ATR_MULT


def compute_triple_barrier_labels(
    df: pd.DataFrame,
    tp_mult: float = TP_ATR_MULT,
    sl_mult: float = SL_ATR_MULT,
    horizon: int = BARRIER_HORIZON,
) -> pd.DataFrame:
    """
    Compute triple-barrier labels for every row in df.

    Input df must contain: symbol_id, trading_date, high, low, close, atr_14.
    Must be sorted by (symbol_id, trading_date).

    Returns a DataFrame with columns:
      symbol_id, trading_date, tb_label (-1/0/+1), tb_label_enc (0/1/2)
    """
    src = df[["symbol_id", "trading_date", "high", "low", "close", "atr_14"]].copy()
    src = src.sort_values(["symbol_id", "trading_date"]).reset_index(drop=True)

    # Drop rows where ATR is missing (early history before rolling window fills)
    valid = src["atr_14"].notna() & src["close"].notna()

    tp_bar = (src["close"] + tp_mult * src["atr_14"]).values
    sl_bar = (src["close"] - sl_mult * src["atr_14"]).values

    # Sentinel: horizon+1 means "barrier never touched"
    sentinel    = float(horizon + 1)
    tp_days     = np.full(len(src), sentinel)
    sl_days     = np.full(len(src), sentinel)

    for d in range(1, horizon + 1):
        # Future High / Low for day d ahead, within each stock group
        fwd_high = src.groupby("symbol_id")["high"].shift(-d).values
        fwd_low  = src.groupby("symbol_id")["low"].shift(-d).values

        # Update first-touch day only where barrier not yet recorded
        tp_hit = (
            ~np.isnan(fwd_high)
            & (fwd_high >= tp_bar)
            & (tp_days == sentinel)
            & valid.values
        )
        sl_hit = (
            ~np.isnan(fwd_low)
            & (fwd_low <= sl_bar)
            & (sl_days == sentinel)
            & valid.values
        )

        tp_days = np.where(tp_hit, float(d), tp_days)
        sl_days = np.where(sl_hit, float(d), sl_days)

    # Assign labels: first-touch wins; tie (same day) → time barrier (0)
    tb_label = np.where(
        tp_days < sl_days,  1,          # TP hit first
        np.where(
            sl_days < tp_days, -1,      # SL hit first
            0,                          # time barrier or tie
        )
    ).astype(np.int8)

    # LightGBM requires 0-indexed classes: -1→0, 0→1, +1→2
    tb_label_enc = (tb_label + 1).astype(np.int8)

    return pd.DataFrame(
        {
            "symbol_id":    src["symbol_id"].values,
            "trading_date": src["trading_date"].values,
            "tb_label":     tb_label,
            "tb_label_enc": tb_label_enc,
        }
    )


def label_distribution(labels: pd.Series) -> dict:
    """Return fractional breakdown of TB label outcomes."""
    counts = labels.value_counts()
    total  = len(labels.dropna())
    return {
        "pct_tp":   counts.get( 1, 0) / total,
        "pct_time": counts.get( 0, 0) / total,
        "pct_sl":   counts.get(-1, 0) / total,
    }
