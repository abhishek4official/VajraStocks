"""
Walk-forward training: LightGBM (primary) + Ridge (benchmark).

Design decisions
────────────────
  Anchored walk-forward: training window grows each fold (no rolling cap).
  This maximises use of history and matches how a live system would retrain.

  Purge + embargo: PURGE_DAYS rows straddling the train/test boundary are
  removed because their 5-day forward return windows overlap with the test
  period.  EMBARGO_DAYS adds an additional gap as a safety margin.

  No early stopping: using the test set as an eval_set for early stopping
  leaks information from the future into the training process.  Instead we
  use a fixed n_estimators with conservative regularisation params.

  Training target: vol-adjusted return (fwd_ret_vol_adj) — normalised
  cross-sectionally so predictions are comparable across stocks.

  Evaluation target: raw return (fwd_ret_5d) for the trading metrics that
  actually matter (hit rate, long-short P&L).
"""

import pickle

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import mstats
from sklearn.linear_model import Ridge
from sklearn.preprocessing import RobustScaler

from VajraML.config import (
    EMBARGO_DAYS,
    LGBM_PARAMS,
    MIN_TRAIN_DAYS,
    MODELS_DIR,
    PURGE_DAYS,
    RIDGE_ALPHA,
    TEST_DAYS,
)
from VajraML.evaluate import evaluate_fold, summarise_results


def walk_forward_train(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str = "fwd_ret_vol_adj",
    raw_ret_col: str = "fwd_ret_5d",
) -> list[dict]:
    """
    Run anchored walk-forward training across all available folds.

    For each fold: trains LightGBM and Ridge, evaluates on the held-out
    test window, saves models to MODELS_DIR/<fold_N>/, and accumulates
    per-fold result dicts.

    Returns the list of fold results (passed to summarise_results).
    """
    trading_dates = sorted(df["trading_date"].dt.date.unique())
    n             = len(trading_dates)
    results       = []
    fold          = 0

    # First test window starts after min training period + purge + embargo
    test_start = MIN_TRAIN_DAYS + PURGE_DAYS + EMBARGO_DAYS

    while test_start + TEST_DAYS <= n:
        fold += 1
        train_end  = test_start - PURGE_DAYS - EMBARGO_DAYS
        test_end   = min(test_start + TEST_DAYS, n)

        train_dates = set(trading_dates[:train_end])
        test_dates  = set(trading_dates[test_start:test_end])

        train = df[df["trading_date"].dt.date.isin(train_dates)].copy()
        test  = df[df["trading_date"].dt.date.isin(test_dates)].copy()

        # Drop rows with NaN target (last FORWARD_DAYS rows per stock at each boundary)
        train = train.dropna(subset=[target_col, raw_ret_col])
        test  = test.dropna(subset=[target_col, raw_ret_col])

        if len(train) < 1_000 or len(test) < 100:
            test_start += TEST_DAYS
            continue

        X_train = train[feature_cols]
        y_train = train[target_col]
        X_test  = test[feature_cols]
        y_test  = test[target_col]

        print(
            f"\nFold {fold}"
            f"  |  train {len(train):,} rows  ({min(train_dates)} to {max(train_dates)})"
            f"  |  test  {len(test):,} rows  ({min(test_dates)} to {max(test_dates)})"
        )

        # Winsorise training labels at 1st/99th percentile.
        # Extreme target values (earnings surprises, circuit hits) would otherwise
        # dominate the loss and cause the model to over-fit to rare events.
        y_train_w = pd.Series(
            mstats.winsorize(y_train.values, limits=[0.01, 0.01]),
            index=y_train.index,
        )

        # ── LightGBM ──────────────────────────────────────────────────────────
        lgbm_model = lgb.LGBMRegressor(**LGBM_PARAMS)
        lgbm_model.fit(X_train, y_train_w)
        lgbm_pred = lgbm_model.predict(X_test)

        # ── Ridge ─────────────────────────────────────────────────────────────
        # RobustScaler is preferred over StandardScaler for financial features:
        # it is less sensitive to outliers (uses median + IQR instead of mean + std).
        # NaN features are filled with 0 (median after scaling) for Ridge only.
        scaler = RobustScaler()
        X_train_s = scaler.fit_transform(X_train.fillna(0))
        X_test_s  = scaler.transform(X_test.fillna(0))

        ridge_model = Ridge(alpha=RIDGE_ALPHA)
        ridge_model.fit(X_train_s, y_train_w)
        ridge_pred = ridge_model.predict(X_test_s)

        # ── Save models ────────────────────────────────────────────────────────
        fold_dir = MODELS_DIR / f"fold_{fold:02d}"
        fold_dir.mkdir(exist_ok=True)

        _lgbm_path = fold_dir / "lgbm.txt"
        lgbm_model.booster_.save_model(str(_lgbm_path))
        # LightGBM on Windows saves CRLF which its own C++ parser can't reload —
        # normalise to LF so models are portable and loadable without retraining.
        _lgbm_path.write_bytes(_lgbm_path.read_bytes().replace(b"\r\n", b"\n"))
        with open(fold_dir / "ridge.pkl", "wb") as fh:
            pickle.dump({"model": ridge_model, "scaler": scaler}, fh)

        # ── Evaluate ──────────────────────────────────────────────────────────
        result = evaluate_fold(
            fold=fold,
            test_df=test,
            lgbm_pred=lgbm_pred,
            ridge_pred=ridge_pred,
            y_true_vol_adj=y_test.values,
            y_true_raw=test[raw_ret_col].values,
            feature_cols=feature_cols,
            lgbm_model=lgbm_model,
        )
        results.append(result)

        test_start += TEST_DAYS

    summarise_results(results)
    return results


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from VajraML.db import get_engine
    from VajraML.pipeline import build_dataset

    print("Connecting to database...")
    engine = get_engine()

    print("Building feature matrix...")
    df, feature_cols = build_dataset(engine)

    print(f"\nDataset  : {df.shape[0]:,} rows x {len(feature_cols)} features")
    print(f"Date range: {df['trading_date'].min().date()} to {df['trading_date'].max().date()}")
    print(f"Target NaN: {df['fwd_ret_vol_adj'].isna().mean():.1%}")

    walk_forward_train(df, feature_cols)
