"""
Side-by-side comparison of VajraML (V1) and VajraML2 (V2).

Reads walk-forward result CSVs from both models and prints a structured
comparison table.  Both models must be trained before running this script.

Run order:
  1. cd VajraStocks && python VajraML/train.py
  2. cd VajraStocks && python VajraML2/train.py
  3. cd VajraStocks && python VajraML2/compare.py

Metrics compared
────────────────
  IC           : V1 Spearman(pred, actual_vol_adj_return)
                 V2 Spearman(P(TP), binary_TP_outcome)
                 Both measure rank signal quality — directly comparable.

  Hit Rate     : V1 hit_rate of top-decile by predicted_return (raw 5d > 0)
                 V2 hit_5d of top-decile by EV score (raw 5d > 0)
                 Same definition — directly comparable.

  L/S Return   : Top-decile long, bottom-decile short, averaged over dates.
                 V1 uses predicted_return for ranking.
                 V2 uses EV score for ranking.
                 Same structure — directly comparable.

  TP Precision : V2 only — fraction of EV-top-decile that hit TP barrier.
                 Context for understanding V2's path-aware signal quality.
"""

import sys
from pathlib import Path

import pandas as pd

V1_RESULTS = Path(__file__).parent.parent / "VajraML"  / "results" / "walk_forward_results.csv"
V2_RESULTS = Path(__file__).parent                     / "results" / "walk_forward_results.csv"


def compare():
    if not V1_RESULTS.exists():
        print(f"VajraML results not found at {V1_RESULTS}")
        print("Run: python VajraML/train.py")
        return

    if not V2_RESULTS.exists():
        print(f"VajraML2 results not found at {V2_RESULTS}")
        print("Run: python VajraML2/train.py")
        return

    v1 = pd.read_csv(V1_RESULTS)
    v2 = pd.read_csv(V2_RESULTS)

    # Align on fold number
    merged = v1[["fold", "lgbm_ic", "lgbm_hit", "ls_lgbm"]].merge(
        v2[["fold", "ic_tp", "tp_prec", "hit_5d", "ls_return"]],
        on="fold",
        how="inner",
    )

    if merged.empty:
        print("No matching folds between V1 and V2. Both must cover the same date range.")
        return

    n = len(merged)

    # ── Fold-by-fold table ────────────────────────────────────────────────────
    print("\n" + "=" * 95)
    print("VajraML vs VajraML2  —  Walk-Forward Comparison")
    print("=" * 95)
    print(
        f"{'':>5}  {'─── VajraML (V1) ───────────────':>36}  "
        f"{'─── VajraML2 (V2) ──────────────────────':>45}"
    )
    print(
        f"{'Fold':<5}  {'IC':>8}  {'Hit%':>8}  {'L/S%':>8}  "
        f"{'IC(P_TP)':>10}  {'TP-Prec@10':>12}  {'Hit5d%':>8}  {'L/S%':>8}"
    )
    print("-" * 95)
    for _, r in merged.iterrows():
        print(
            f"{int(r['fold']):<5}  "
            f"{r['lgbm_ic']:>+8.4f}  {r['lgbm_hit']:>8.1%}  {r['ls_lgbm']:>+8.2%}  "
            f"{r['ic_tp']:>+10.4f}  {r['tp_prec']:>12.1%}  {r['hit_5d']:>8.1%}  {r['ls_return']:>+8.2%}"
        )
    print("-" * 95)

    # ── Summary row ──────────────────────────────────────────────────────────
    v1_ic_mean  = merged["lgbm_ic"].mean()
    v2_ic_mean  = merged["ic_tp"].mean()
    v1_ic_std   = merged["lgbm_ic"].std()
    v2_ic_std   = merged["ic_tp"].std()

    v1_icir = v1_ic_mean / (v1_ic_std + 1e-8)
    v2_icir = v2_ic_mean / (v2_ic_std + 1e-8)

    print(
        f"{'Mean':<5}  "
        f"{v1_ic_mean:>+8.4f}  {merged['lgbm_hit'].mean():>8.1%}  {merged['ls_lgbm'].mean():>+8.2%}  "
        f"{v2_ic_mean:>+10.4f}  {merged['tp_prec'].mean():>12.1%}  {merged['hit_5d'].mean():>8.1%}  {merged['ls_return'].mean():>+8.2%}"
    )
    print(
        f"{'ICIR':<5}  {v1_icir:>+8.3f}  {'':>8}  {'':>8}  "
        f"{v2_icir:>+10.3f}"
    )
    print("=" * 95)

    # ── Head-to-head verdict ──────────────────────────────────────────────────
    print("\nHEAD-TO-HEAD VERDICT")
    print("-" * 50)
    _verdict("IC Signal Quality",   v1_ic_mean,               v2_ic_mean,               higher_is_better=True)
    _verdict("IC Consistency (IR)", v1_icir,                  v2_icir,                  higher_is_better=True)
    _verdict("Hit Rate (5d raw)",   merged["lgbm_hit"].mean(), merged["hit_5d"].mean(),  higher_is_better=True)
    _verdict("L/S Return",          merged["ls_lgbm"].mean(),  merged["ls_return"].mean(), higher_is_better=True)
    print("-" * 50)

    wins_v2 = sum([
        v2_ic_mean  > v1_ic_mean,
        v2_icir     > v1_icir,
        merged["hit_5d"].mean()    > merged["lgbm_hit"].mean(),
        merged["ls_return"].mean() > merged["ls_lgbm"].mean(),
    ])
    winner = "VajraML2 (Triple-Barrier Classifier)" if wins_v2 >= 3 else "VajraML (Volatility-Adjusted Regressor)"
    print(f"\nOVERALL WINNER: {winner}  ({wins_v2}/4 metrics)")

    # Interpretation note
    print("\nNote: IC scales differ — V1 correlates against vol-adj Sharpe,")
    print("V2 correlates P(TP) against binary TP outcome.  Hit Rate and L/S")
    print("Return use identical definitions and are the fairest comparison.")


def _verdict(metric: str, v1_val: float, v2_val: float, higher_is_better: bool):
    margin = abs(v1_val - v2_val)
    if higher_is_better:
        winner = "V2" if v2_val > v1_val else "V1"
    else:
        winner = "V2" if v2_val < v1_val else "V1"
    print(f"  {metric:<28}  V1={v1_val:>+8.4f}  V2={v2_val:>+8.4f}  → {winner}  (Δ={margin:.4f})")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))
    compare()
