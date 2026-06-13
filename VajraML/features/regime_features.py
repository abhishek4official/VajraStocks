"""
Phase 4 — Market regime features from Nifty 50 (^NSEI).

These features provide context about the broad market environment so the
model can distinguish between signals firing in a trending regime versus a
choppy one.  A stock breaking out in a bull market carries different weight
than the same breakout during a broad sell-off.

Returns a date-keyed DataFrame that is left-joined to the stock feature matrix.

Changes from v1:
  - Replaced binary nifty_above_ema20 with continuous nifty_vs_ema20 (% distance)
  - Added nifty_vs_ema50  (medium-term trend strength)
  - Added nifty_vs_sma200 (long-term structural bull/bear context)
  - Added nifty_high_vol_flag (binary: 1 when market vol is elevated vs recent history)
"""

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine


def compute_regime_features(engine: Engine) -> pd.DataFrame:
    """
    Load Nifty 50 daily prices and derive regime context features.

    Tries both '^NSEI' and 'NSEI' symbol names to handle variations in
    how the index was synced from yfinance.
    """
    query = text("""
        SELECT p.trading_date,
               CAST(p.adj_close AS FLOAT) AS adj_close,
               CAST(p.[close]   AS FLOAT) AS [close]
        FROM daily_prices p
        JOIN symbols s ON s.id = p.symbol_id
        WHERE s.symbol IN ('^NSEI', 'NSEI', '^NIFTY50')
          AND p.granularity = '1d'
        ORDER BY p.trading_date
    """)
    nifty = pd.read_sql(query, engine, parse_dates=["trading_date"])

    if nifty.empty:
        raise ValueError(
            "Nifty 50 data not found in daily_prices (tried ^NSEI, NSEI, ^NIFTY50). "
            "Run a sync from the VajraStocks app first."
        )

    nifty = nifty.sort_values("trading_date").reset_index(drop=True)
    ac = nifty["adj_close"]

    # Rolling returns
    nifty["nifty_ret_5d"]  = np.log(ac / ac.shift(5))
    nifty["nifty_ret_20d"] = np.log(ac / ac.shift(20))

    # Continuous % distance from moving averages (replaces binary above/below flag)
    ema20  = ac.ewm(span=20,  adjust=False).mean()
    ema50  = ac.ewm(span=50,  adjust=False).mean()
    sma200 = ac.rolling(200,  min_periods=100).mean()

    nifty["nifty_vs_ema20"]  = (ac - ema20)  / ema20   # was binary nifty_above_ema20
    nifty["nifty_vs_ema50"]  = (ac - ema50)  / ema50   # medium-term trend strength
    nifty["nifty_vs_sma200"] = (ac - sma200) / sma200  # structural bull/bear context

    # 20-day realised vol (annualised) — market fear / calm proxy
    log_ret = np.log(ac / ac.shift(1))
    nifty["nifty_vol_20d"] = log_ret.rolling(20, min_periods=10).std() * np.sqrt(252)

    # High-vol regime flag: 1 when current vol is in top quintile of last 90 trading days
    # Low importance (187 vs 2549 for nifty_vol_20d) — kept to match trained model feature count
    nifty["nifty_high_vol_flag"] = (
        nifty["nifty_vol_20d"]
        > nifty["nifty_vol_20d"].rolling(90, min_periods=30).quantile(0.80)
    ).astype(float)

    regime_cols = [
        "trading_date",
        "nifty_ret_5d",
        "nifty_ret_20d",
        "nifty_vs_ema20",
        "nifty_vs_ema50",
        "nifty_vs_sma200",
        "nifty_vol_20d",
        "nifty_high_vol_flag",
    ]
    return nifty[regime_cols]
