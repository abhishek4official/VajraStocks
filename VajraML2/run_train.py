"""Standalone training runner — adds VajraStocks root to sys.path then runs V2 training."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from VajraML.db import get_engine
from VajraML2.pipeline2 import build_training_dataset
from VajraML2.train import walk_forward_train_v2

if __name__ == "__main__":
    engine = get_engine()
    df, feature_cols = build_training_dataset(engine)
    print(f"Dataset: {len(df):,} rows x {len(feature_cols)} features", flush=True)
    walk_forward_train_v2(df, feature_cols)
