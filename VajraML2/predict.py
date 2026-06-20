"""
VajraML2 inference: probability-based predictions for the latest trading date.

Signal pipeline (applied in order)
────────────────────────────────────
  1. Regime Gate     — if nifty_vs_sma200 < -0.05 OR nifty_high_vol_flag == 1
                       all grades become "Market Risk"; no longs.
  2. Volume Filter   — stock must have volume_ratio_20d >= 1.2 (above-avg volume)
                       to qualify for Buy/Strong Buy.
  3. Dual-Model      — V1 (regressor) rank_pct > 0.80  AND  V2 P(TP) > 0.40
                       required for Buy or Strong Buy.

Output columns per stock
────────────────────────
  p_tp          — P(take-profit hit first)
  p_sl          — P(stop-loss hit first)
  p_neutral     — P(time barrier / neither)
  ev_score      — Dimensionless EV: P(TP)×1.5 − P(SL)×1.0
  v1_rank_pct   — V1 regressor rank percentile (0→worst, 1→best)
  volume_ok     — True if volume_ratio_20d >= 1.2
  signal_grade  — "Strong Buy" / "Buy" / "Watch" / "Avoid" / "Market Risk"
  ev_rank       — Rank by EV score (1 = highest EV)

Usage
─────
  python predict.py           # LightGBM classifier only
  python predict.py --all     # Also print full ranked table
"""

import argparse
import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from VajraML2.config import (
    MODELS_DIR,
    REGIME_SMA200_FLOOR,
    RESULTS_DIR,
    SL_ATR_MULT,
    TP_ATR_MULT,
    V1_RANK_PCT_MIN,
    V2_PTP_MIN,
    VOLUME_MIN_RATIO,
)
from VajraML2.evaluate import ev_score

_V1_MODELS_DIR = Path(__file__).parent.parent / "VajraML" / "models"


def predict_latest_v2() -> pd.DataFrame:
    """
    Generate probability predictions for all universe stocks on the latest date.

    Returns a DataFrame sorted by ev_rank (1 = best) with per-stock probabilities,
    EV score, signal grade, and filter diagnostics.
    """
    from VajraML.db import get_engine
    from VajraML2.pipeline2 import build_inference_dataset

    engine = get_engine()
    df, feature_cols = build_inference_dataset(engine)

    latest_date = df["trading_date"].max()
    latest = df[df["trading_date"] == latest_date].copy()
    print(f"Predicting for {latest_date.date()} — {len(latest)} stocks")

    # ── Load most recent V2 fold model ───────────────────────────────────────
    fold_dirs = sorted(MODELS_DIR.glob("fold_*"))
    if not fold_dirs:
        raise FileNotFoundError(
            f"No trained models in {MODELS_DIR}.\nRun `python run_train.py` first."
        )
    latest_fold = fold_dirs[-1]
    print(f"V2 model: {latest_fold.name}")

    # Feature list: use saved JSON if available (crossover-dropped set),
    # otherwise fall back to build_inference_dataset's list.
    fc_path = latest_fold / "feature_cols.json"
    if fc_path.exists():
        v2_feature_cols = json.loads(fc_path.read_text())
    else:
        v2_feature_cols = feature_cols

    booster_v2 = lgb.Booster(
        model_str=(latest_fold / "lgbm_v2.txt").read_text(encoding="utf-8")
    )
    X_v2 = latest[v2_feature_cols].values
    proba = booster_v2.predict(X_v2)   # shape (n, 3)
    p_sl   = proba[:, 0]
    p_time = proba[:, 1]
    p_tp   = proba[:, 2]
    ev     = ev_score(p_tp, p_sl)

    # ── V1 dual-model ranking ─────────────────────────────────────────────────
    v1_fold_dirs = sorted(_V1_MODELS_DIR.glob("fold_*"))
    # prefer fold_final; fall back to latest fold_NN
    v1_model_path = _V1_MODELS_DIR / "fold_final" / "lgbm.txt"
    if not v1_model_path.exists() and v1_fold_dirs:
        v1_model_path = v1_fold_dirs[-1] / "lgbm.txt"

    if v1_model_path.exists():
        print(f"V1 model: {v1_model_path.parent.name}")
        booster_v1 = lgb.Booster(model_str=v1_model_path.read_text(encoding="utf-8"))
        # Use V1's own feature names — handles V1 having crossover features
        v1_feature_names = booster_v1.feature_name()
        X_v1 = latest[v1_feature_names].values
        v1_pred = booster_v1.predict(X_v1)   # shape (n,) — regression score
        v1_rank_pct = pd.Series(v1_pred).rank(pct=True).values
    else:
        print("V1 model not found — dual-model agreement disabled")
        v1_rank_pct = np.zeros(len(latest))

    # ── Regime gate (market-wide) ─────────────────────────────────────────────
    nifty_vs_sma200  = float(latest["nifty_vs_sma200"].iloc[0])
    nifty_high_vol   = int(latest["nifty_high_vol_flag"].iloc[0])
    regime_ok = (nifty_vs_sma200 > REGIME_SMA200_FLOOR) and (nifty_high_vol == 0)

    if not regime_ok:
        print(
            f"\n[REGIME GATE TRIGGERED]"
            f"\n  nifty_vs_sma200 = {nifty_vs_sma200:+.3f}  (floor: {REGIME_SMA200_FLOOR:+.3f})"
            f"\n  nifty_high_vol  = {nifty_high_vol}"
            f"\n  All signals overridden to 'Market Risk' — no longs recommended."
        )
    else:
        print(
            f"Regime OK — nifty_vs_sma200={nifty_vs_sma200:+.3f}, high_vol={nifty_high_vol}"
        )

    # ── Assemble results ──────────────────────────────────────────────────────
    results = latest[["symbol_id", "symbol", "trading_date"]].copy().reset_index(drop=True)
    results["p_tp"]              = p_tp
    results["p_neutral"]         = p_time
    results["p_sl"]              = p_sl
    results["ev_score"]          = ev
    results["v1_rank_pct"]       = v1_rank_pct
    results["volume_ratio_20d"]  = latest["volume_ratio_20d"].values
    results["volume_ok"]         = results["volume_ratio_20d"] >= VOLUME_MIN_RATIO
    results["nifty_vs_sma200"]   = nifty_vs_sma200
    results["nifty_high_vol"]    = nifty_high_vol

    results["signal_grade"] = results.apply(
        lambda r: _grade(r, regime_ok), axis=1
    )
    results["ev_rank"] = results["ev_score"].rank(ascending=False).astype(int)

    results = results.sort_values("ev_rank").reset_index(drop=True)
    return results


def _grade(row, regime_ok: bool) -> str:
    if not regime_ok:
        return "Market Risk"
    ev  = row["ev_score"]
    ptp = row["p_tp"]
    vol_ok    = row["volume_ok"]
    dual_agree = (
        row["v1_rank_pct"] > V1_RANK_PCT_MIN
        and ptp > V2_PTP_MIN
        and ev > 0
    )
    if dual_agree and vol_ok and ptp >= 0.45:
        return "Strong Buy"
    if dual_agree and vol_ok and ptp >= 0.40:
        return "Buy"
    if ev > 0:
        return "Watch"
    return "Avoid"


def run_ml2_snapshot_update(engine) -> int:
    """
    Run V2 predictions for all universe stocks and write results to screening_snapshots.

    Columns written: ml2_p_tp, ml2_p_sl, ml2_ev_score, ml2_rank, ml2_signal.
    Called as a post-sync hook — uses the app's existing engine, no second connection.
    Returns the number of snapshot rows updated.
    """
    from sqlalchemy import text
    from VajraML2.pipeline2 import build_inference_dataset

    print("VajraML2: building inference dataset for post-sync V2 update...")
    df, feature_cols = build_inference_dataset(engine)

    latest_date = df["trading_date"].max()
    latest = df[df["trading_date"] == latest_date].copy()
    print(f"VajraML2: predicting {len(latest)} stocks for {latest_date.date()}")

    # ── Load V2 model ─────────────────────────────────────────────────────────
    v2_model_path = MODELS_DIR / "fold_final" / "lgbm_v2.txt"
    if not v2_model_path.exists():
        fold_dirs = sorted(MODELS_DIR.glob("fold_*"))
        if not fold_dirs:
            raise FileNotFoundError(
                f"No V2 models in {MODELS_DIR}. Run VajraML2 training first."
            )
        v2_model_path = fold_dirs[-1] / "lgbm_v2.txt"

    fc_path = v2_model_path.parent / "feature_cols.json"
    if fc_path.exists():
        v2_feature_cols = json.loads(fc_path.read_text())
    else:
        v2_feature_cols = feature_cols

    booster_v2 = lgb.Booster(model_str=v2_model_path.read_text(encoding="utf-8"))
    proba = booster_v2.predict(latest[v2_feature_cols].values)
    p_sl   = proba[:, 0]
    p_tp   = proba[:, 2]
    ev     = ev_score(p_tp, p_sl)

    # ── Load V1 model for dual-model agreement ────────────────────────────────
    v1_model_path = _V1_MODELS_DIR / "fold_final" / "lgbm.txt"
    if not v1_model_path.exists():
        v1_fold_dirs = sorted(_V1_MODELS_DIR.glob("fold_*"))
        v1_model_path = v1_fold_dirs[-1] / "lgbm.txt" if v1_fold_dirs else None

    if v1_model_path and v1_model_path.exists():
        booster_v1 = lgb.Booster(model_str=v1_model_path.read_text(encoding="utf-8"))
        v1_feature_names = booster_v1.feature_name()
        v1_pred = booster_v1.predict(latest[v1_feature_names].values)
        v1_rank_pct = pd.Series(v1_pred).rank(pct=True).values
    else:
        v1_rank_pct = np.zeros(len(latest))

    # ── Regime gate ───────────────────────────────────────────────────────────
    nifty_vs_sma200 = float(latest["nifty_vs_sma200"].iloc[0])
    nifty_high_vol  = int(latest["nifty_high_vol_flag"].iloc[0])
    regime_ok = (nifty_vs_sma200 > REGIME_SMA200_FLOOR) and (nifty_high_vol == 0)

    # ── Assemble result DataFrame ─────────────────────────────────────────────
    result = latest[["symbol_id", "volume_ratio_20d"]].copy().reset_index(drop=True)
    result["p_tp"]        = p_tp
    result["p_sl"]        = p_sl
    result["ev_score"]    = ev
    result["v1_rank_pct"] = v1_rank_pct
    result["volume_ok"]   = result["volume_ratio_20d"] >= VOLUME_MIN_RATIO

    result["ml2_signal"] = result.apply(lambda r: _grade(r, regime_ok), axis=1)
    result["ml2_rank"]   = result["ev_score"].rank(ascending=False).astype(int)

    # ── Bulk write to screening_snapshots ─────────────────────────────────────
    # V2 is the primary ML signal — writes to both ml2_* and the shared ml_* columns.
    updated = 0
    with engine.begin() as conn:
        for _, row in result.iterrows():
            conn.execute(
                text("""
                    UPDATE screening_snapshots
                    SET ml2_p_tp      = :p_tp,
                        ml2_p_sl      = :p_sl,
                        ml2_ev_score  = :ev,
                        ml2_rank      = :rank,
                        ml2_signal    = :signal
                    WHERE symbol_id = :sid
                """),
                {
                    "p_tp":   float(row["p_tp"]),
                    "p_sl":   float(row["p_sl"]),
                    "ev":     float(row["ev_score"]),
                    "rank":   int(row["ml2_rank"]),
                    "signal": str(row["ml2_signal"]),
                    "sid":    int(row["symbol_id"]),
                },
            )
            updated += 1

    print(f"VajraML2: V2 snapshot update complete — {updated} rows written for {latest_date.date()}")
    return updated


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    parser = argparse.ArgumentParser(
        description="VajraML2 — triple-barrier probability predictions"
    )
    parser.add_argument("--all", action="store_true", help="Print full ranked table")
    args = parser.parse_args()

    preds = predict_latest_v2()

    strong_buy = preds[preds["signal_grade"] == "Strong Buy"]
    buy        = preds[preds["signal_grade"] == "Buy"]
    watch      = preds[preds["signal_grade"] == "Watch"]
    mkt_risk   = preds[preds["signal_grade"] == "Market Risk"]

    print(f"\n── Grade summary ──────────────────────────────────────────────")
    if len(mkt_risk):
        print(f"  *** Market Risk — regime gate active, {len(mkt_risk)} stocks flagged ***")
    print(f"  Strong Buy : {len(strong_buy):>4}  ({len(strong_buy)/len(preds):.1%})")
    print(f"  Buy        : {len(buy):>4}  ({len(buy)/len(preds):.1%})")
    print(f"  Watch      : {len(watch):>4}  ({len(watch)/len(preds):.1%})")
    print(f"  Avoid      : {len(preds)-len(strong_buy)-len(buy)-len(watch)-len(mkt_risk):>4}")
    print(
        f"\n── Filter stats ───────────────────────────────────────────────"
        f"\n  Volume OK (≥{VOLUME_MIN_RATIO}×):  {preds['volume_ok'].sum():>4} / {len(preds)}"
        f"\n  V1 top-20%:            {(preds['v1_rank_pct'] > V1_RANK_PCT_MIN).sum():>4} / {len(preds)}"
        f"\n  V2 P(TP)≥{V2_PTP_MIN}:         {(preds['p_tp'] >= V2_PTP_MIN).sum():>4} / {len(preds)}"
        f"\n  Dual-model agree:      {((preds['v1_rank_pct']>V1_RANK_PCT_MIN)&(preds['p_tp']>=V2_PTP_MIN)&(preds['ev_score']>0)).sum():>4} / {len(preds)}"
    )

    cols = ["ev_rank", "symbol", "p_tp", "p_sl", "ev_score", "v1_rank_pct",
            "volume_ok", "signal_grade"]

    if len(strong_buy):
        print("\n── Strong Buy ─────────────────────────────────────────────────")
        print(strong_buy[cols].head(30).to_string(index=False))

    if len(buy):
        print("\n── Buy ────────────────────────────────────────────────────────")
        print(buy[cols].head(20).to_string(index=False))

    if args.all:
        print("\n── Full ranked table ──────────────────────────────────────────")
        print(preds[cols].to_string(index=False))

    out = RESULTS_DIR / "latest_predictions_v2.csv"
    preds.to_csv(out, index=False)
    print(f"\nFull predictions saved → {out}")
