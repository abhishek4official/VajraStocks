"""
VajraML2 configuration.

Extends VajraML with triple-barrier target parameters and a LightGBM
classifier setup.  Feature engineering and walk-forward split parameters
are inherited from VajraML.config to keep the comparison fair.
"""

from pathlib import Path

# ── Shared parameters — kept identical to VajraML for fair comparison ─────────
from VajraML.config import (
    DB_CONN_STR,
    UNIVERSE_TOP_N,
    UNIVERSE_MIN_DAYS,
    MIN_TRAIN_DAYS,
    TEST_DAYS,
    PURGE_DAYS,
    EMBARGO_DAYS,
    FORWARD_DAYS,
)

# ── Triple-Barrier parameters ─────────────────────────────────────────────────
# Asymmetric 3:2 reward/risk ratio — TP is larger than SL to require a higher
# P(TP) before the expected value turns positive.
TP_ATR_MULT     = 1.5   # Take-profit: entry + 1.5 × ATR (calm regime)
SL_ATR_MULT     = 1.0   # Stop-loss:   entry - 1.0 × ATR (calm regime)
BARRIER_HORIZON = FORWARD_DAYS  # Max holding days — same window as VajraML

# Dynamic barriers for high-volatility regime (nifty_high_vol_flag == 1).
# Wider multipliers filter noise during choppy periods — a sustained move
# is required before the barrier counts as TP or SL.
TP_ATR_MULT_HIGH_VOL = 2.0   # wider TP in high-vol
SL_ATR_MULT_HIGH_VOL = 1.5   # wider SL in high-vol (avoid premature stop-out)

# ── Filters applied at inference time ────────────────────────────────────────
# Regime gate: no new longs when market is below 200-day SMA or in high vol
REGIME_SMA200_FLOOR = -0.05   # nifty_vs_sma200 threshold for bearish gate

# Volume confirmation: stock must have above-average volume to confirm signal
VOLUME_MIN_RATIO    = 1.2     # volume_ratio_20d minimum

# Dual-model agreement: V1 rank and V2 P(TP) must both clear thresholds
V1_RANK_PCT_MIN     = 0.80    # V1 must rank stock in top-20% of universe
V2_PTP_MIN          = 0.40    # V2 must give P(TP) ≥ 40%

# ── Crossover features to drop before training (item 6) ──────────────────────
# 12 "days_since_*" features ranked 73-89/93 with avg 11.4% of top importance.
# Dropping them removes noise and shrinks the feature space by ~13%.
CROSSOVER_FEATURES = frozenset([
    "days_since_bull_xover",      "days_since_bear_xover",
    "days_since_price_sma20_bull","days_since_price_sma50_bull",
    "days_since_price_ema20_bull","days_since_ema9_ema20_bull",
    "days_since_ema9_ema20_bear", "days_since_sma20_sma50_bull",
    "days_since_macd_bull",       "days_since_macd_bear",
    "days_since_cmf_bull",        "days_since_cmf_bear",
])

# LightGBM class encoding (must be 0-indexed consecutive integers)
TB_CLASS_SL   = 0   # Stop-loss hit first
TB_CLASS_TIME = 1   # Time barrier (neither hit within horizon)
TB_CLASS_TP   = 2   # Take-profit hit first

# ── LightGBM Classifier ───────────────────────────────────────────────────────
# Architecture is identical to VajraML's regressor except:
#   - objective / metric changed for 3-class classification
#   - class_weight="balanced" compensates for unequal TP/SL/time frequencies
LGBM_PARAMS_V2 = {
    "objective":          "multiclass",
    "num_class":          3,
    "metric":             "multi_logloss",
    "n_estimators":       800,
    "learning_rate":      0.02,
    "num_leaves":         127,
    "max_depth":          7,
    "min_child_samples":  100,
    "subsample":          0.7,
    "subsample_freq":     1,
    "colsample_bytree":   0.7,
    "reg_alpha":          0.1,
    "reg_lambda":         1.0,
    "class_weight":       "balanced",
    "random_state":       42,
    "verbose":           -1,
    "n_jobs":            -1,
}

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT_DIR    = Path(__file__).parent
MODELS_DIR  = ROOT_DIR / "models"
RESULTS_DIR = ROOT_DIR / "results"

MODELS_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)
