"""
VajraML backtest — replay fold predictions as weekly swing trades.

Strategy
────────
  Signal day : First trading day of each calendar week in the fold test window
  Entry      : Open price on T+1  (day after signal)
  Exit       : Open price on T+6  (5 trading days after entry)
  Universe   : Top-4 by ML rank from volume-qualified pool on signal day
  Filter 1   : 20-day avg daily volume 100K–2M shares  (mid-cap sweet spot)
  Filter 2   : Nifty above its 200-day SMA               (regime gate)
  Cost       : 0.30% round-trip per trade
  Position   : ₹50,000 per stock (equal weight)

Output
──────
  results/backtest_trades.csv   — every individual trade
  results/backtest_summary.csv  — per-fold aggregated metrics
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import lightgbm as lgb
import numpy as np
import pandas as pd

from VajraML.config import (
    EMBARGO_DAYS,
    MIN_TRAIN_DAYS,
    MODELS_DIR,
    PURGE_DAYS,
    RESULTS_DIR,
    TEST_DAYS,
)
from VajraML.db import get_engine
from VajraML.pipeline import build_dataset

# ── Strategy parameters ───────────────────────────────────────────────────────
TOP_N          = 4           # long basket size (top-4 from qualified pool)
VOLUME_MIN     = 100_000     # 20-day avg daily volume floor (shares)
VOLUME_MAX     = 2_000_000   # 20-day avg daily volume ceiling (shares)
COST_RT        = 0.003       # 0.30% round-trip cost per trade
POSITION_SIZE  = 50_000      # ₹ per position (equal weight)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fold_test_windows(trading_dates: list) -> list[dict]:
    """
    Reconstruct the test date set for each fold using the same walk-forward
    logic as train.py — deterministic from config constants.
    Only includes folds whose saved model directory exists.
    """
    n      = len(trading_dates)
    folds  = []
    fold   = 0
    test_start = MIN_TRAIN_DAYS + PURGE_DAYS + EMBARGO_DAYS

    while test_start + TEST_DAYS <= n:
        fold += 1
        test_end   = min(test_start + TEST_DAYS, n)
        test_dates = set(trading_dates[test_start:test_end])
        fold_dir   = MODELS_DIR / f"fold_{fold:02d}"

        if fold_dir.exists() and (fold_dir / "lgbm.txt").exists():
            folds.append({
                "fold":       fold,
                "test_dates": test_dates,
                "fold_dir":   fold_dir,
                "date_min":   min(test_dates),
                "date_max":   max(test_dates),
            })

        test_start += TEST_DAYS

    return folds


def _weekly_signal_days(test_dates: set) -> list:
    """
    Return the first available trading day of each calendar week
    within the test date set (handles NSE holidays on Mondays).
    """
    dates      = sorted(test_dates)
    signals    = []
    seen_weeks = set()

    for d in dates:
        week_key = d.isocalendar()[:2]   # (ISO year, ISO week number)
        if week_key not in seen_weeks:
            seen_weeks.add(week_key)
            signals.append(d)

    return signals


def _add_open_to_open_return(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add open-to-open 5-day return to df.
    Uses groupby-shift so gaps never bleed across stock boundaries.

      entry_open  = open on T+1  (shift -1 within group)
      exit_open   = open on T+6  (shift -6 within group)
      ret_oto_5d  = (exit - entry) / entry
    """
    df = df.sort_values(["symbol_id", "trading_date"]).copy()
    g  = df.groupby("symbol_id")["open"]

    df["entry_open"] = g.shift(-1)
    df["exit_open"]  = g.shift(-6)
    df["ret_oto_5d"] = (df["exit_open"] - df["entry_open"]) / df["entry_open"]

    return df


# ── Main backtest ─────────────────────────────────────────────────────────────

def run_backtest() -> pd.DataFrame:
    print("Connecting to database...")
    engine = get_engine()

    print("Building full feature matrix (this takes a few minutes)...")
    df, feature_cols = build_dataset(engine)

    # 20-day avg daily volume — derived from existing feature to avoid a DB round-trip.
    # volume_ratio_20d = volume / avg_vol  →  avg_vol = volume / volume_ratio_20d
    df["avg_vol_20d"] = df["volume"] / df["volume_ratio_20d"]

    # Open-to-open 5-day return (more realistic than close-to-close target)
    print("Computing open-to-open trade returns...")
    df = _add_open_to_open_return(df)

    trading_dates = sorted(df["trading_date"].dt.date.unique())
    folds         = _fold_test_windows(trading_dates)

    if not folds:
        print(f"No trained fold models found in {MODELS_DIR}. Run train.py first.")
        return pd.DataFrame()

    print(f"\nReplaying {len(folds)} folds as live trades...\n")
    all_trades = []

    for fi in folds:
        fold_num   = fi["fold"]
        test_dates = fi["test_dates"]
        fold_dir   = fi["fold_dir"]

        # Load fold model
        booster = lgb.Booster(
            model_str=(fold_dir / "lgbm.txt").read_text(encoding="utf-8")
        )

        # Slice to this fold's test window
        test_df = df[df["trading_date"].dt.date.isin(test_dates)].copy()

        # Score every stock on every test day
        test_df["lgbm_pred"] = booster.predict(test_df[feature_cols].values)

        # Rank within each date (1 = highest predicted return)
        test_df["ml_rank"] = (
            test_df
            .groupby("trading_date")["lgbm_pred"]
            .rank(ascending=False, method="first")
            .astype(int)
        )

        signal_days  = _weekly_signal_days(test_dates)
        fold_trades  = 0

        for signal_day in signal_days:
            day_df = test_df[test_df["trading_date"].dt.date == signal_day]

            # ── Apply all filters, then take top-N from qualified pool ──────
            # Volume + regime filter first so TOP_N picks from qualified
            # stocks, not necessarily from global ranks 1-4.
            qualified = day_df[
                (day_df["avg_vol_20d"]     >= VOLUME_MIN) &
                (day_df["avg_vol_20d"]     <= VOLUME_MAX) &
                (day_df["nifty_vs_sma200"] >  0)         &   # Nifty above 200MA
                (day_df["nifty_vs_ema50"]  >  0)             # Nifty above 50MA
            ]
            candidates = (
                qualified
                .sort_values("ml_rank")   # lowest rank number = highest conviction
                .head(TOP_N)
            )

            if candidates.empty:
                continue

            for _, row in candidates.iterrows():
                # Skip if open prices are unavailable (last few rows of dataset)
                if pd.isna(row["ret_oto_5d"]) or pd.isna(row["entry_open"]):
                    continue

                gross_ret = float(row["ret_oto_5d"])
                net_ret   = gross_ret - COST_RT
                pnl       = net_ret * POSITION_SIZE

                all_trades.append({
                    "fold":        fold_num,
                    "signal_date": signal_day,
                    "test_start":  fi["date_min"],
                    "test_end":    fi["date_max"],
                    "symbol":      row["symbol"],
                    "ml_rank":     int(row["ml_rank"]),
                    "lgbm_pred":   round(float(row["lgbm_pred"]), 6),
                    "avg_vol_20d": int(row["avg_vol_20d"]) if not pd.isna(row["avg_vol_20d"]) else None,
                    "entry_open":  round(float(row["entry_open"]), 2),
                    "exit_open":   round(float(row["exit_open"]), 2),
                    "gross_ret":   round(gross_ret, 6),
                    "net_ret":     round(net_ret, 6),
                    "pnl_inr":     round(pnl, 2),
                    "win":         int(net_ret > 0),
                })
                fold_trades += 1

        print(
            f"Fold {fold_num}  |  {fi['date_min']} to {fi['date_max']}"
            f"  |  {len(signal_days)} signal weeks"
            f"  |  {fold_trades:,} trades"
        )

    if not all_trades:
        print(
            "\nNo trades generated.\n"
            "Possible causes:\n"
            "  • Regime gate (nifty_vs_sma200 > 0) blocked all signal days\n"
            "  • Volume filter too strict\n"
            "  • Missing open prices in DailyPrice table\n"
            "Try running without the regime gate first to isolate the issue."
        )
        return pd.DataFrame()

    trades = pd.DataFrame(all_trades)

    # Cumulative P&L across all folds (sorted by signal date, then fold)
    trades_sorted = trades.sort_values(["fold", "signal_date", "ml_rank"])
    trades_sorted["cumulative_pnl"] = trades_sorted["pnl_inr"].cumsum()
    trades = trades_sorted.reset_index(drop=True)

    # ── Save trade log ────────────────────────────────────────────────────────
    trades_path = RESULTS_DIR / "backtest_trades.csv"
    trades.to_csv(trades_path, index=False)
    print(f"\nTrade log -> {trades_path}  ({len(trades):,} trades)")

    # ── Per-fold summary ──────────────────────────────────────────────────────
    summary = (
        trades.groupby(["fold", "test_start", "test_end"])
        .agg(
            n_trades     = ("pnl_inr", "count"),
            hit_rate     = ("win", "mean"),
            avg_gross    = ("gross_ret", "mean"),
            avg_net      = ("net_ret", "mean"),
            best_trade   = ("net_ret", "max"),
            worst_trade  = ("net_ret", "min"),
            total_pnl    = ("pnl_inr", "sum"),
        )
        .reset_index()
    )

    summary_path = RESULTS_DIR / "backtest_summary.csv"
    summary.to_csv(summary_path, index=False)


    # ── Print summary ─────────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print(f"BACKTEST  |  Top-{TOP_N} weekly swing  |  Rs.{POSITION_SIZE:,}/position  |  {COST_RT:.1%} cost")
    print(f"          |  Volume {VOLUME_MIN:,} - {VOLUME_MAX:,} shares  |  Regime gate: Nifty > 200MA AND > 50MA")
    print("=" * 78)

    fmt = {
        "hit_rate":    "{:.1%}",
        "avg_gross":   "{:+.2%}",
        "avg_net":     "{:+.2%}",
        "best_trade":  "{:+.2%}",
        "worst_trade": "{:+.2%}",
        "total_pnl":   "Rs.{:,.0f}",
    }
    display = summary.copy()
    for col, f in fmt.items():
        display[col] = display[col].apply(lambda x: f.format(x))

    print(display.to_string(index=False))
    print("=" * 78)

    # ── Overall stats ─────────────────────────────────────────────────────────
    print(f"\nTotal trades      : {len(trades):,}")
    print(f"Overall hit rate  : {trades['win'].mean():.1%}")
    print(f"Avg net per trade : {trades['net_ret'].mean():+.2%}")
    print(f"Avg gross/trade   : {trades['gross_ret'].mean():+.2%}")
    print(f"Best trade        : {trades['net_ret'].max():+.2%}")
    print(f"Worst trade       : {trades['net_ret'].min():+.2%}")
    print(f"Total P&L         : Rs.{trades['pnl_inr'].sum():,.0f}")

    # Regime-blocked weeks
    all_signal_count = sum(
        len(_weekly_signal_days(fi["test_dates"]))
        for fi in _fold_test_windows(trading_dates)
    )
    print(f"\nSignal weeks total   : {all_signal_count}")
    print(f"Summary saved        -> {summary_path}")

    return trades


if __name__ == "__main__":
    run_backtest()
