"""
Main feature pipeline.

Orchestrates Phases 1-5 in strict sequence and returns the clean feature
matrix together with the target variable, ready for walk-forward training.

Phase sequence
──────────────
  1  Price-derived features    (returns, candle, vol, 52w-high)
  2  Indicator transforms      (ratio normalisation, OBV fix, crossover days)
  3  Cross-sectional ranks     (percentile rank within universe per date)
  4  Market regime features    (Nifty-derived context, joined by date)
  5  Lag features              (1/2/3/5-day lags of selected features)
  T  Target attachment         (joined last, by key only — no value leakage)
"""

import datetime

import pandas as pd
from sqlalchemy import BigInteger, Float, Integer, cast, select
from sqlalchemy.engine import Engine

from stocks.db.models import DailyIndicator, DailyPrice, Symbol

from VajraML.config import FORWARD_DAYS, LAG_DAYS, LAG_FEATURES
from VajraML.features.cross_sectional import compute_cross_sectional_ranks
from VajraML.features.indicator_features import compute_indicator_features
from VajraML.features.price_features import compute_price_features
from VajraML.features.regime_features import compute_regime_features
from VajraML.target import compute_targets
from VajraML.universe import get_universe_symbol_ids

# ── Columns excluded from the feature set ────────────────────────────────────
# Raw source columns whose transformed versions are features instead.
_NON_FEATURE = {
    # identifiers / metadata
    "id", "symbol_id", "symbol", "company_name", "trading_date", "granularity",
    # raw OHLCV (transformed versions are features)
    "open", "high", "low", "close", "adj_close", "volume",
    # raw MAs replaced by close_vs_* % distance
    "ema_9", "ema_20", "ema_21",
    "sma_20", "sma_50",
    # raw BB replaced by bb_pct_b / bb_bandwidth
    "bb_upper", "bb_middle", "bb_lower",
    # raw supertrend replaced by close_vs_supertrend + supertrend_dir_enc
    "supertrend", "supertrend_dir",
    # raw ATR replaced by atr_pct
    "atr_14",
    # raw DI replaced by di_diff
    "plus_di", "minus_di",
    # raw OBV replaced by obv_ret_5d / obv_vs_ma20
    "obv",
    # crossover booleans replaced by days_since_* recency features
    "stochrsi_bullish_xover", "stochrsi_bearish_xover",
    # target columns — never features
    "fwd_ret_5d", "fwd_ret_vol_adj", "return_label",
}


def build_dataset(
    engine: Engine,
    since_date: datetime.date | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Build the complete feature matrix + target for the top-700 universe.

    Parameters
    ----------
    since_date : If given, load only rows on or after this date.
                 Use for inference (prediction) to avoid reloading 3 years of
                 history when only the latest date is needed.
                 Leave as None for training (needs full history).

    Returns
    -------
    df          : DataFrame containing identifiers, features, and target columns.
    feature_cols: Ordered list of feature column names (excludes identifiers and targets).
    """
    # ── Universe ──────────────────────────────────────────────────────────────
    print("Selecting top-700 universe...")
    symbol_ids = get_universe_symbol_ids(engine)

    # ── Load prices ───────────────────────────────────────────────────────────
    print("Loading prices...")
    prices_stmt = (
        select(
            DailyPrice.symbol_id,
            Symbol.symbol,
            DailyPrice.trading_date,
            cast(DailyPrice.open,      Float).label("open"),
            cast(DailyPrice.high,      Float).label("high"),
            cast(DailyPrice.low,       Float).label("low"),
            cast(DailyPrice.close,     Float).label("close"),
            cast(DailyPrice.adj_close, Float).label("adj_close"),
            cast(DailyPrice.volume,    BigInteger).label("volume"),
        )
        .join(Symbol, Symbol.id == DailyPrice.symbol_id)
        .where(
            DailyPrice.symbol_id.in_(symbol_ids),
            DailyPrice.granularity == "1d",
            *([DailyPrice.trading_date >= since_date] if since_date else []),
        )
        .order_by(DailyPrice.symbol_id, DailyPrice.trading_date)
    )
    prices = pd.read_sql(prices_stmt, engine, parse_dates=["trading_date"])

    # ── Load indicators ───────────────────────────────────────────────────────
    print("Loading indicators...")
    indicators_stmt = (
        select(
            DailyIndicator.symbol_id,
            DailyIndicator.trading_date,
            DailyIndicator.rsi_14,
            DailyIndicator.atr_14,
            DailyIndicator.sma_20,
            DailyIndicator.sma_50,
            DailyIndicator.ema_9,
            DailyIndicator.ema_20,
            DailyIndicator.ema_21,
            DailyIndicator.macd_line,
            DailyIndicator.macd_signal,
            DailyIndicator.macd_histogram,
            DailyIndicator.bb_upper,
            DailyIndicator.bb_middle,
            DailyIndicator.bb_lower,
            DailyIndicator.adx_14,
            DailyIndicator.plus_di,
            DailyIndicator.minus_di,
            DailyIndicator.obv,
            DailyIndicator.supertrend,
            DailyIndicator.supertrend_dir,
            DailyIndicator.stoch_k,
            DailyIndicator.stoch_d,
            DailyIndicator.cmf_20,
            DailyIndicator.stochrsi_k,
            DailyIndicator.stochrsi_d,
            cast(DailyIndicator.stochrsi_bullish_xover, Integer).label("stochrsi_bullish_xover"),
            cast(DailyIndicator.stochrsi_bearish_xover, Integer).label("stochrsi_bearish_xover"),
        )
        .where(
            DailyIndicator.symbol_id.in_(symbol_ids),
            DailyIndicator.granularity == "1d",
            *([DailyIndicator.trading_date >= since_date] if since_date else []),
        )
    )
    indicators = pd.read_sql(indicators_stmt, engine, parse_dates=["trading_date"])

    # ── Compute target (ISOLATED) ─────────────────────────────────────────────
    # Target is computed from prices alone and stored separately.
    # It is only joined by key at the very end of this function.
    print("Computing targets...")
    prices_sorted = prices.sort_values(["symbol_id", "trading_date"])
    targets = compute_targets(prices_sorted, forward_days=FORWARD_DAYS)

    # ── Phase 1: Price features ───────────────────────────────────────────────
    print("Phase 1 — price features...")
    prices_feat = compute_price_features(prices_sorted)

    # ── Join prices + indicators ──────────────────────────────────────────────
    print("Joining prices + indicators...")
    df = prices_feat.merge(indicators, on=["symbol_id", "trading_date"], how="inner")

    # ── Phase 2: Indicator transforms ────────────────────────────────────────
    print("Phase 2 — indicator transforms...")
    df = compute_indicator_features(df)

    # ── Phase 3: Cross-sectional ranks ───────────────────────────────────────
    print("Phase 3 — cross-sectional ranks...")
    df = compute_cross_sectional_ranks(df)

    # ── Phase 4: Market regime ────────────────────────────────────────────────
    print("Phase 4 — regime features...")
    regime = compute_regime_features(engine)
    df = df.merge(regime, on="trading_date", how="left")

    # ── Phase 5: Lag features ─────────────────────────────────────────────────
    # Sort by (symbol, date) before shifting — groupby.shift() respects stock
    # boundaries so lags never cross from one stock's last row into the next.
    print("Phase 5 — lag features...")
    df = df.sort_values(["symbol_id", "trading_date"])
    for lag in LAG_DAYS:
        for feat in LAG_FEATURES:
            if feat in df.columns:
                df[f"{feat}_lag{lag}"] = df.groupby("symbol_id")[feat].shift(lag)

    # ── Attach targets ────────────────────────────────────────────────────────
    df = df.merge(
        targets[["symbol_id", "trading_date", "fwd_ret_5d", "fwd_ret_vol_adj", "return_label"]],
        on=["symbol_id", "trading_date"],
        how="left",
    )

    # ── Derive feature column list ─────────────────────────────────────────────
    feature_cols = [c for c in df.columns if c not in _NON_FEATURE]

    print(
        f"\nDataset ready: {len(df):,} rows x {len(feature_cols)} features "
        f"| {df['trading_date'].min().date()} to {df['trading_date'].max().date()}"
    )
    return df, feature_cols


if __name__ == "__main__":
    from VajraML.db import get_engine

    engine = get_engine()
    df, feature_cols = build_dataset(engine)

    print(f"\nFeatures ({len(feature_cols)}):")
    for i, f in enumerate(feature_cols, 1):
        print(f"  {i:>3}. {f}")

    print(f"\nTarget NaN %  fwd_ret_5d     : {df['fwd_ret_5d'].isna().mean():.1%}")
    print(f"Target NaN %  fwd_ret_vol_adj: {df['fwd_ret_vol_adj'].isna().mean():.1%}")
    print(f"\nLabel distribution:\n{df['return_label'].value_counts()}")
