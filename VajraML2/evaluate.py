"""
Evaluation metrics for VajraML2 (triple-barrier classifier).

Metrics are designed to be partially comparable with VajraML so that
compare.py can show a fair side-by-side view.

Classifier-specific metrics
───────────────────────────
  TP Precision@10%  — Among the top 10% of stocks ranked by P(TP), what
                      fraction actually hit the take-profit barrier first?
                      Equivalent of VajraML hit rate but path-aware.

  IC (P_TP)         — Spearman rank correlation between P(TP) and the binary
                      TP outcome (1 if TP hit, else 0).  Comparable to V1 IC.

  EV Score          — Dimensionless expected value proxy used for ranking:
                      EV = P(TP) × TP_ATR_MULT − P(SL) × SL_ATR_MULT
                      Positive EV → expected profitable trade.

Shared (comparable) metrics
────────────────────────────
  Hit Rate 5d       — Top-10% by EV: fraction with positive raw 5d return.
                      Same definition as VajraML hit rate for direct comparison.

  L/S Return        — Long top-decile, short bottom-decile by EV score,
                      averaged over test-set dates.  Same as VajraML L/S metric.
"""

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from VajraML2.config import RESULTS_DIR, SL_ATR_MULT, TB_CLASS_TP, TP_ATR_MULT


def ev_score(p_tp: np.ndarray, p_sl: np.ndarray) -> np.ndarray:
    """Dimensionless EV proxy — positive means expected profitable trade."""
    return p_tp * TP_ATR_MULT - p_sl * SL_ATR_MULT


def evaluate_fold_v2(
    fold: int,
    test_df: pd.DataFrame,
    proba: np.ndarray,          # shape (n, 3): [P(SL), P(Time), P(TP)]
    tb_label: np.ndarray,       # actual TB labels (-1, 0, +1)
    raw_ret: np.ndarray,        # actual raw 5d return for shared metrics
    feature_cols: list[str],
    lgbm_model=None,
) -> dict:
    """Compute all metrics for one fold and print a summary."""
    p_sl   = proba[:, 0]
    p_time = proba[:, 1]
    p_tp   = proba[:, 2]
    ev     = ev_score(p_tp, p_sl)

    # Binary TP outcome for IC computation
    actual_tp = (tb_label == 1).astype(float)

    # ── Classifier metrics ────────────────────────────────────────────────────
    ic_tp        = _ic(p_tp, actual_tp)
    tp_prec      = _precision_topk(p_tp, actual_tp, top_pct=0.10)
    ev_prec      = _precision_topk(ev, actual_tp,   top_pct=0.10)

    # ── Shared metrics (comparable to VajraML) ────────────────────────────────
    hit_5d       = _hit_rate_topk(ev, raw_ret, top_pct=0.10)
    ls_ret       = _long_short_return(test_df, ev, raw_ret)

    print(
        f"  IC(P_TP)={ic_tp:+.4f}  "
        f"TP-Prec@10%={tp_prec:.1%}  "
        f"EV-Prec@10%={ev_prec:.1%}  "
        f"Hit5d@10%={hit_5d:.1%}  "
        f"L/S={ls_ret:+.2%}"
    )

    result = {
        "fold":       fold,
        "ic_tp":      ic_tp,
        "tp_prec":    tp_prec,
        "ev_prec":    ev_prec,
        "hit_5d":     hit_5d,
        "ls_return":  ls_ret,
        "pct_ev_pos": float((ev > 0).mean()),
    }

    if lgbm_model is not None and hasattr(lgbm_model, "feature_importances_"):
        fi = pd.Series(lgbm_model.feature_importances_, index=feature_cols)
        fi = fi.sort_values(ascending=False)
        fi.to_csv(RESULTS_DIR / f"feature_importance_fold{fold:02d}.csv")
        result["top10_features"] = fi.head(10).index.tolist()
        print(f"  Top-5 features: {fi.head(5).index.tolist()}")

    return result


def summarise_results_v2(results: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(results)

    ic_mean   = df["ic_tp"].mean()
    ic_std    = df["ic_tp"].std()
    icir      = ic_mean / (ic_std + 1e-8)

    prec_mean  = df["tp_prec"].mean()
    hit_mean   = df["hit_5d"].mean()
    ls_mean    = df["ls_return"].mean()

    print("\n" + "=" * 80)
    print("VajraML2 WALK-FORWARD SUMMARY  (Triple-Barrier Classifier)")
    print("=" * 80)
    print(
        f"{'Fold':<5} {'IC(P_TP)':>10} {'TP-Prec@10':>12} "
        f"{'Hit5d@10':>10} {'L/S Ret':>10} {'EV>0%':>8}"
    )
    print("-" * 80)
    for r in results:
        print(
            f"{r['fold']:<5} {r['ic_tp']:>+10.4f} {r['tp_prec']:>12.1%} "
            f"{r['hit_5d']:>10.1%} {r['ls_return']:>+10.2%} {r['pct_ev_pos']:>8.1%}"
        )
    print("-" * 80)
    print(
        f"{'Mean':<5} {ic_mean:>+10.4f} {prec_mean:>12.1%} "
        f"{hit_mean:>10.1%} {ls_mean:>+10.2%}"
    )
    print(f"{'ICIR':<5} {icir:>+10.3f}")
    print("=" * 80)

    df.to_csv(RESULTS_DIR / "walk_forward_results.csv", index=False)
    return df


# ── Internal helpers ──────────────────────────────────────────────────────────

def _ic(pred: np.ndarray, actual: np.ndarray) -> float:
    mask = ~(np.isnan(pred) | np.isnan(actual))
    if mask.sum() < 10:
        return 0.0
    return float(spearmanr(pred[mask], actual[mask]).statistic)


def _precision_topk(score: np.ndarray, actual_tp: np.ndarray, top_pct: float) -> float:
    """Fraction of top-k stocks (by score) that actually hit TP."""
    mask = ~(np.isnan(score) | np.isnan(actual_tp))
    if mask.sum() < 10:
        return 0.0
    s = score[mask]
    a = actual_tp[mask]
    cutoff  = int(len(s) * top_pct)
    cutoff  = max(1, cutoff)
    top_idx = np.argsort(s)[-cutoff:]
    return float(a[top_idx].mean())


def _hit_rate_topk(score: np.ndarray, raw_ret: np.ndarray, top_pct: float) -> float:
    """Fraction of top-k stocks (by score) with positive raw 5d return."""
    mask = ~(np.isnan(score) | np.isnan(raw_ret))
    if mask.sum() < 10:
        return 0.5
    s = score[mask]
    r = raw_ret[mask]
    cutoff  = max(1, int(len(s) * top_pct))
    top_idx = np.argsort(s)[-cutoff:]
    return float((r[top_idx] > 0).mean())


def _long_short_return(
    test_df: pd.DataFrame,
    score: np.ndarray,
    raw_ret: np.ndarray,
    top_pct: float = 0.10,
) -> float:
    """Long top-decile, short bottom-decile by EV score, averaged across dates."""
    tmp = test_df[["trading_date"]].copy()
    tmp["score"]  = score
    tmp["actual"] = raw_ret
    tmp = tmp.dropna(subset=["score", "actual"])

    def _date_ls(grp: pd.DataFrame) -> float:
        n = len(grp)
        if n < 10:
            return 0.0
        cutoff = max(1, int(n * top_pct))
        ranked = grp.sort_values("score")
        return ranked.tail(cutoff)["actual"].mean() - ranked.head(cutoff)["actual"].mean()

    ls_series = tmp.groupby("trading_date").apply(_date_ls)
    return float(ls_series.mean())
