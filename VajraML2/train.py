"""
VajraML2 walk-forward training: LightGBM classifier (primary) +
Logistic Regression (benchmark).

Architecture changes vs VajraML
────────────────────────────────
  Target      : tb_label_enc ∈ {0, 1, 2}  (SL / Time / TP class)
                instead of fwd_ret_vol_adj (continuous Sharpe)

  Model       : LGBMClassifier (multiclass) instead of LGBMRegressor.
                predict_proba() returns [P(SL), P(Time), P(TP)] per stock.

  Benchmark   : LogisticRegression (L2) instead of Ridge.
                Same RobustScaler preprocessing.

  No winsorise: Classification targets are discrete — winsorisation does
                not apply.

Everything else (anchored walk-forward, purge/embargo, GPU params,
feature matrix) is IDENTICAL to VajraML for a fair comparison.
"""

import json
import lightgbm as lgb
import numpy as np
import pandas as pd

from VajraML2.config import (
    EMBARGO_DAYS,
    LGBM_PARAMS_V2,
    MIN_TRAIN_DAYS,
    MODELS_DIR,
    PURGE_DAYS,
    TEST_DAYS,
)
from VajraML2.evaluate import evaluate_fold_v2, summarise_results_v2


def walk_forward_train_v2(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str = "tb_label_enc",
    raw_ret_col: str = "fwd_ret_5d",
) -> list[dict]:
    """
    Run anchored walk-forward training across all folds.

    For each fold: trains LGBMClassifier and LogisticRegression, evaluates
    on the held-out test window, saves models to MODELS_DIR/<fold_N>/,
    and accumulates per-fold result dicts.
    """
    trading_dates = sorted(df["trading_date"].dt.date.unique())
    n             = len(trading_dates)
    results       = []
    fold          = 0

    test_start = MIN_TRAIN_DAYS + PURGE_DAYS + EMBARGO_DAYS

    while test_start + TEST_DAYS <= n:
        fold += 1
        train_end  = test_start - PURGE_DAYS - EMBARGO_DAYS
        test_end   = min(test_start + TEST_DAYS, n)

        train_dates = set(trading_dates[:train_end])
        test_dates  = set(trading_dates[test_start:test_end])

        train = df[df["trading_date"].dt.date.isin(train_dates)].copy()
        test  = df[df["trading_date"].dt.date.isin(test_dates)].copy()

        # Drop rows where TB labels are missing (last BARRIER_HORIZON rows
        # per stock at the boundary have no forward prices to label)
        train = train.dropna(subset=[target_col, raw_ret_col])
        test  = test.dropna(subset=[target_col, raw_ret_col])

        if len(train) < 1_000 or len(test) < 100:
            test_start += TEST_DAYS
            continue

        X_train  = train[feature_cols]
        y_train  = train[target_col].astype(int)
        X_test   = test[feature_cols]
        tb_test  = test["tb_label"].values         # raw -1/0/+1 for evaluate
        raw_test = test[raw_ret_col].values

        print(
            f"\nFold {fold}"
            f"  |  train {len(train):,} rows  ({min(train_dates)} to {max(train_dates)})"
            f"  |  test  {len(test):,} rows  ({min(test_dates)} to {max(test_dates)})"
        )

        # Print TB label distribution in training fold
        for cls, name in [( 2, "TP"), (1, "Time"), (0, "SL")]:
            pct = (y_train == cls).mean()
            print(f"    {name}: {pct:.1%}", end="  ")
        print()

        # ── LightGBM Classifier ───────────────────────────────────────────────
        lgbm_model = lgb.LGBMClassifier(**LGBM_PARAMS_V2)
        lgbm_model.fit(X_train, y_train)
        lgbm_proba = lgbm_model.predict_proba(X_test)   # (n, 3)

        # ── Save model ────────────────────────────────────────────────────────
        fold_dir = MODELS_DIR / f"fold_{fold:02d}"
        fold_dir.mkdir(exist_ok=True)

        lgbm_path = fold_dir / "lgbm_v2.txt"
        lgbm_model.booster_.save_model(str(lgbm_path))
        lgbm_path.write_bytes(lgbm_path.read_bytes().replace(b"\r\n", b"\n"))

        # Save exact feature list used — predict.py needs this when crossover
        # features differ between V1 and V2 models.
        (fold_dir / "feature_cols.json").write_text(json.dumps(feature_cols))

        # ── Evaluate primary model ────────────────────────────────────────────
        result = evaluate_fold_v2(
            fold=fold,
            test_df=test,
            proba=lgbm_proba,
            tb_label=tb_test,
            raw_ret=raw_test,
            feature_cols=feature_cols,
            lgbm_model=lgbm_model,
        )

        results.append(result)
        test_start += TEST_DAYS

    summarise_results_v2(results)
    return results


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from VajraML.db import get_engine
    from VajraML2.pipeline2 import build_training_dataset

    print("Connecting to database...")
    engine = get_engine()

    print("Building feature matrix + triple-barrier labels...")
    df, feature_cols = build_training_dataset(engine)

    print(f"\nDataset  : {df.shape[0]:,} rows × {len(feature_cols)} features")
    print(f"Date range: {df['trading_date'].min().date()} to {df['trading_date'].max().date()}")
    print(f"TB label NaN: {df['tb_label_enc'].isna().mean():.1%}")

    walk_forward_train_v2(df, feature_cols)
