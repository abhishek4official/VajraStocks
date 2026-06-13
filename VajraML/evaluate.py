"""
Evaluation metrics for financial ML models.

These metrics measure trading usefulness, not standard ML accuracy.
A model can have 55% accuracy (worse than a coin flip naive guess on
a 60/40 class split) and still be highly profitable if it consistently
puts the best stocks at the top of the ranking.

Key metrics
───────────
  IC   — Information Coefficient: Spearman rank correlation between
          predicted and actual returns.  IC > 0.05 is useful, > 0.10
          is strong for daily stock prediction.
  ICIR — IC / std(IC) across folds: measures signal consistency.
          ICIR > 0.5 is good; > 1.0 is excellent.
  Hit  — Fraction of long predictions that realise a positive raw return.
  L/S  — Average long-short daily return (long top decile, short bottom).
"""

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from VajraML.config import RESULTS_DIR


def evaluate_fold(
    fold: int,
    test_df: pd.DataFrame,
    lgbm_pred: np.ndarray,
    ridge_pred: np.ndarray,
    y_true_vol_adj: np.ndarray,
    y_true_raw: np.ndarray,
    feature_cols: list[str],
    lgbm_model=None,
) -> dict:
    """Compute all metrics for one walk-forward fold and print a summary."""
    lgbm_ic  = _ic(lgbm_pred,  y_true_vol_adj)
    ridge_ic = _ic(ridge_pred, y_true_vol_adj)

    lgbm_hit  = _hit_rate(lgbm_pred,  y_true_raw)
    ridge_hit = _hit_rate(ridge_pred, y_true_raw)

    ls_lgbm  = _long_short_return(test_df, lgbm_pred,  y_true_raw)
    ls_ridge = _long_short_return(test_df, ridge_pred, y_true_raw)

    print(f"  LGBM   IC={lgbm_ic:+.4f}  Hit={lgbm_hit:.1%}  L/S={ls_lgbm:+.2%}")
    print(f"  Ridge  IC={ridge_ic:+.4f}  Hit={ridge_hit:.1%}  L/S={ls_ridge:+.2%}")

    result = {
        "fold":      fold,
        "lgbm_ic":   lgbm_ic,
        "ridge_ic":  ridge_ic,
        "lgbm_hit":  lgbm_hit,
        "ridge_hit": ridge_hit,
        "ls_lgbm":   ls_lgbm,
        "ls_ridge":  ls_ridge,
    }

    if lgbm_model is not None and hasattr(lgbm_model, "feature_importances_"):
        fi = pd.Series(lgbm_model.feature_importances_, index=feature_cols)
        fi = fi.sort_values(ascending=False)
        fi.to_csv(RESULTS_DIR / f"feature_importance_fold{fold:02d}.csv")
        result["top10_features"] = fi.head(10).index.tolist()
        print(f"  Top-5 features: {fi.head(5).index.tolist()}")

    return result


def summarise_results(results: list[dict]) -> pd.DataFrame:
    """Aggregate fold results, print ICIR, and recommend ensemble vs single model."""
    df = pd.DataFrame(results)

    lgbm_ic_mean   = df["lgbm_ic"].mean()
    lgbm_ic_std    = df["lgbm_ic"].std()
    ridge_ic_mean  = df["ridge_ic"].mean()
    ridge_ic_std   = df["ridge_ic"].std()

    lgbm_icir  = lgbm_ic_mean  / (lgbm_ic_std  + 1e-8)
    ridge_icir = ridge_ic_mean / (ridge_ic_std + 1e-8)

    print("\n" + "=" * 65)
    print("WALK-FORWARD SUMMARY")
    print("=" * 65)
    print(f"{'Fold':<5} {'LGBM IC':>9} {'Ridge IC':>9} {'LGBM Hit':>9} {'L/S':>9}")
    print("-" * 65)
    for r in results:
        print(
            f"{r['fold']:<5} {r['lgbm_ic']:>+9.4f} {r['ridge_ic']:>+9.4f} "
            f"{r['lgbm_hit']:>9.1%} {r['ls_lgbm']:>+9.2%}"
        )
    print("-" * 65)
    print(f"{'Mean':<5} {lgbm_ic_mean:>+9.4f} {ridge_ic_mean:>+9.4f}")
    print(f"{'ICIR':<5} {lgbm_icir:>+9.3f} {ridge_icir:>+9.3f}")
    print("=" * 65)

    # Ensemble recommendation based on IC gap
    if lgbm_ic_mean > 2 * ridge_ic_mean:
        rec = "Use LightGBM alone  (IC > 2x Ridge — non-linear signals dominate)"
    elif abs(lgbm_ic_mean - ridge_ic_mean) < 0.02:
        rec = "Ensemble recommended  (models have similar IC — genuine diversity)"
    else:
        rec = "Use LightGBM  (clearly outperforms Ridge)"
    print(f"\nRECOMMENDATION: {rec}\n")

    df.to_csv(RESULTS_DIR / "walk_forward_results.csv", index=False)
    return df


# ── Internal helpers ──────────────────────────────────────────────────────────

def _ic(pred: np.ndarray, actual: np.ndarray) -> float:
    """Spearman rank correlation between predictions and actual returns."""
    mask = ~(np.isnan(pred) | np.isnan(actual))
    if mask.sum() < 10:
        return 0.0
    return float(spearmanr(pred[mask], actual[mask]).statistic)


def _hit_rate(pred: np.ndarray, actual_raw: np.ndarray) -> float:
    """Fraction of positive-predicted stocks that delivered positive raw returns."""
    mask = ~(np.isnan(pred) | np.isnan(actual_raw))
    long_mask = mask & (pred > 0)
    if long_mask.sum() == 0:
        return 0.5
    return float((actual_raw[long_mask] > 0).mean())


def _long_short_return(
    test_df: pd.DataFrame,
    pred: np.ndarray,
    actual_raw: np.ndarray,
    top_pct: float = 0.10,
) -> float:
    """
    Simple long-short backtest: long top decile, short bottom decile by
    predicted return rank per date.  Returns the average daily L/S spread.
    """
    tmp = test_df[["trading_date"]].copy()
    tmp["pred"]   = pred
    tmp["actual"] = actual_raw
    tmp = tmp.dropna(subset=["pred", "actual"])

    def _date_ls(grp: pd.DataFrame) -> float:
        n = len(grp)
        if n < 10:
            return 0.0
        cutoff = max(1, int(n * top_pct))
        ranked = grp.sort_values("pred")
        return ranked.tail(cutoff)["actual"].mean() - ranked.head(cutoff)["actual"].mean()

    ls_series = tmp.groupby("trading_date").apply(_date_ls)
    return float(ls_series.mean())
