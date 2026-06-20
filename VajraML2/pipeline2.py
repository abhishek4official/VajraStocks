"""
VajraML2 dataset builder.

Wraps the VajraML feature pipeline (identical feature engineering) and
attaches triple-barrier labels as the training target.

Two entry points:
  build_training_dataset()  — full history, includes tb_label columns.
  build_inference_dataset() — limited lookback (for live prediction).
                              Does NOT attach TB labels (no future prices).
"""

import datetime

from sqlalchemy.engine import Engine

from VajraML.pipeline import build_dataset
from VajraML2.config import CROSSOVER_FEATURES
from VajraML2.target_barrier import compute_triple_barrier_labels, label_distribution


def build_training_dataset(engine: Engine):
    """
    Build the complete feature matrix with triple-barrier labels.

    Returns
    -------
    df          : Full feature DataFrame including tb_label and tb_label_enc.
    feature_cols: Feature column list with crossover features removed.
    """
    print("=== VajraML2 training dataset ===")
    df, feature_cols = build_dataset(engine)  # full history, no since_date

    # Drop low-importance crossover features (ranked 73-89/93 in V1 walk-forward)
    before = len(feature_cols)
    feature_cols = [c for c in feature_cols if c not in CROSSOVER_FEATURES]
    print(f"Dropped {before - len(feature_cols)} crossover features -> {len(feature_cols)} remain")

    # Compute triple-barrier labels using high/low/atr_14 already in df
    print("Computing triple-barrier labels...")
    df = df.sort_values(["symbol_id", "trading_date"])
    tb = compute_triple_barrier_labels(df)

    df = df.merge(
        tb[["symbol_id", "trading_date", "tb_label", "tb_label_enc"]],
        on=["symbol_id", "trading_date"],
        how="left",
    )

    dist = label_distribution(df["tb_label"].dropna())
    print(
        f"TB label distribution — "
        f"TP: {dist['pct_tp']:.1%}  "
        f"Time: {dist['pct_time']:.1%}  "
        f"SL: {dist['pct_sl']:.1%}"
    )

    return df, feature_cols


def build_inference_dataset(engine: Engine):
    """
    Build feature matrix for live prediction (last ~400 calendar days).
    No triple-barrier labels — model outputs probabilities directly.
    """
    since_date = datetime.date.today() - datetime.timedelta(days=400)
    print(f"=== VajraML2 inference dataset (since {since_date}) ===")
    df, feature_cols = build_dataset(engine, since_date=since_date)
    feature_cols = [c for c in feature_cols if c not in CROSSOVER_FEATURES]
    return df, feature_cols
