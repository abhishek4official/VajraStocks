"""
Inference: generate 5-day return predictions for the latest trading date.

Loads the most recent fold's LightGBM model (and optionally Ridge) and
ranks all 700 universe stocks by predicted return.

Usage
─────
  python predict.py                  # LightGBM only
  python predict.py --ensemble       # Average LightGBM + Ridge
"""

import argparse
import datetime
import pickle
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from VajraML.config import MODELS_DIR, RESULTS_DIR
from VajraML.db import get_engine
from VajraML.pipeline import build_dataset


def predict_latest(use_ensemble: bool = False) -> pd.DataFrame:
    """
    Generate predictions for all universe stocks on the latest trading date.

    Returns a DataFrame sorted by rank (1 = most bullish) with columns:
      symbol, trading_date, lgbm_pred, predicted_return, return_label, rank
    """
    engine = get_engine()

    since_date = datetime.date.today() - datetime.timedelta(days=400)
    print(f"Building feature matrix (since {since_date})...")
    df, feature_cols = build_dataset(engine, since_date=since_date)

    latest_date = df["trading_date"].max()
    latest      = df[df["trading_date"] == latest_date].copy()
    print(f"Predicting for {latest_date.date()} — {len(latest)} stocks")

    # ── Load most recent fold models ──────────────────────────────────────────
    fold_dirs = sorted(MODELS_DIR.glob("fold_*"))
    if not fold_dirs:
        raise FileNotFoundError(
            f"No trained models found in {MODELS_DIR}.\n"
            "Run `python train.py` first."
        )
    latest_fold = fold_dirs[-1]
    print(f"Using models from {latest_fold.name}")

    X = latest[feature_cols]

    # ── LightGBM prediction ───────────────────────────────────────────────────
    booster   = lgb.Booster(model_str=(latest_fold / "lgbm.txt").read_text(encoding="utf-8"))
    lgbm_pred = booster.predict(X.values)

    results = latest[["symbol_id", "symbol", "trading_date"]].copy()
    results["lgbm_pred"] = lgbm_pred

    # ── Optional Ridge ensemble ───────────────────────────────────────────────
    if use_ensemble:
        ridge_path = latest_fold / "ridge.pkl"
        with open(ridge_path, "rb") as fh:
            bundle = pickle.load(fh)
        X_s        = bundle["scaler"].transform(X.fillna(0))
        ridge_pred = bundle["model"].predict(X_s)
        results["ridge_pred"]      = ridge_pred
        results["predicted_return"] = (lgbm_pred + ridge_pred) / 2
    else:
        results["predicted_return"] = lgbm_pred

    # ── Rank and label ────────────────────────────────────────────────────────
    results["rank"]         = results["predicted_return"].rank(ascending=False).astype(int)
    results["return_label"] = results["rank"].apply(
        _label_from_rank, n=len(results)
    )

    results = results.sort_values("rank").reset_index(drop=True)
    return results


def _label_from_rank(rank: int, n: int) -> str:
    pct = rank / n
    if pct <= 0.10:
        return "Very Bullish"
    if pct <= 0.30:
        return "Bullish"
    if pct <= 0.70:
        return "Neutral"
    if pct <= 0.90:
        return "Bearish"
    return "Very Bearish"


def run_ml_snapshot_update(engine) -> int:
    """
    Run ML predictions for all universe stocks and write results to screening_snapshots.

    Called as a post-sync hook from the VajraStocks sync engine.  Uses the app's
    existing SQLAlchemy engine so no second DB connection is opened.

    Returns the number of snapshot rows updated.
    """
    from sqlalchemy import text

    # For inference we only need the last ~280 trading days (~400 calendar days).
    # The longest lookback in price features is HIGH_LOOKBACK=252 trading days
    # (52-week high). Loading 400 calendar days always covers that window with
    # a safe buffer, avoiding the full 3-year / 489K-row rebuild on every sync.
    since_date = datetime.date.today() - datetime.timedelta(days=400)

    print(f"VajraML: building feature matrix for post-sync ML update (since {since_date})...")
    df, feature_cols = build_dataset(engine, since_date=since_date)

    latest_date = df["trading_date"].max()
    latest = df[df["trading_date"] == latest_date].copy()
    print(f"VajraML: predicting {len(latest)} stocks for {latest_date.date()}")

    fold_dirs = sorted(MODELS_DIR.glob("fold_*"))
    if not fold_dirs:
        raise FileNotFoundError(
            f"No trained models found in {MODELS_DIR}. Run VajraML/train.py first."
        )

    # Read via text mode so Python normalises CRLF→LF on Windows before passing to
    # LightGBM's C++ parser, which rejects \r in numeric fields regardless of platform.
    booster = lgb.Booster(model_str=(fold_dirs[-1] / "lgbm.txt").read_text(encoding="utf-8"))
    X = latest[feature_cols]
    latest = latest.copy()
    latest["ml_prediction"] = booster.predict(X.values)

    n = len(latest)
    latest["ml_rank"] = latest["ml_prediction"].rank(ascending=False).astype(int)
    latest["ml_label"] = latest["ml_rank"].apply(_label_from_rank, n=n)

    updated = 0
    with engine.begin() as conn:
        for _, row in latest.iterrows():
            conn.execute(
                text("""
                    UPDATE screening_snapshots
                    SET ml_prediction = :pred,
                        ml_rank       = :rank,
                        ml_label      = :label
                    WHERE symbol_id = :sid
                """),
                {
                    "pred":  float(row["ml_prediction"]),
                    "rank":  int(row["ml_rank"]),
                    "label": str(row["ml_label"]),
                    "sid":   int(row["symbol_id"]),
                },
            )
            updated += 1

    print(f"VajraML: ML snapshot update complete — {updated} rows written for {latest_date.date()}")
    return updated


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VajraML — predict 5-day stock returns")
    parser.add_argument("--ensemble", action="store_true", help="Average LightGBM + Ridge")
    args = parser.parse_args()

    preds = predict_latest(use_ensemble=args.ensemble)

    print("\n── Top 30 (Very Bullish / Bullish) ──────────────────────────────")
    display_cols = ["rank", "symbol", "predicted_return", "return_label"]
    if args.ensemble:
        display_cols += ["lgbm_pred", "ridge_pred"]
    print(preds.head(30)[display_cols].to_string(index=False))

    print("\n── Bottom 10 (Very Bearish) ─────────────────────────────────────")
    print(preds.tail(10)[display_cols].to_string(index=False))

    out = RESULTS_DIR / "latest_predictions.csv"
    preds.to_csv(out, index=False)
    print(f"\nFull predictions saved -> {out}")
