from pathlib import Path

# ── Database ──────────────────────────────────────────────────────────────────
DB_CONN_STR = (
    "mssql+pyodbc://(localdb)\\MSSQLLocalDB/vajra_stocks"
    "?driver=ODBC+Driver+17+for+SQL+Server"
    "&trusted_connection=yes"
    "&encrypt=no"
)

# ── Universe ──────────────────────────────────────────────────────────────────
UNIVERSE_TOP_N    = 700
UNIVERSE_MIN_DAYS = 200   # min trading days in last 365 calendar days

# ── Feature engineering ───────────────────────────────────────────────────────
ROLLING_VOL_WINDOW = 20
VOLUME_AVG_WINDOW  = 20
HIGH_LOOKBACK      = 252   # 52-week high (replaces sma_200)
OBV_CHANGE_WINDOW  = 5
OBV_MA_WINDOW      = 20
XOVER_CAP_DAYS     = 20    # cap for days_since_crossover

LAG_DAYS = [1, 2, 3, 5]
LAG_FEATURES = [
    "rsi_14",
    "macd_histogram",
    "log_ret_1d",
    "volume_ratio_20d",
    "adx_14",
    "cmf_20",
    # supertrend_dir_enc removed — near-zero importance across all folds
]

# ── Target ────────────────────────────────────────────────────────────────────
FORWARD_DAYS = 5

RETURN_THRESHOLDS = {
    "Very Bearish": (float("-inf"), -0.05),
    "Bearish":      (-0.05,        -0.02),
    "Neutral":      (-0.02,         0.02),
    "Bullish":      ( 0.02,         0.05),
    "Very Bullish": ( 0.05,  float("inf")),
}

# ── Walk-forward validation ───────────────────────────────────────────────────
MIN_TRAIN_DAYS = 350   # trading days in first training window
TEST_DAYS      = 60    # trading days per fold (~3 months)
PURGE_DAYS     = 5     # equals FORWARD_DAYS — prevents target leakage at boundary
EMBARGO_DAYS   = 5     # additional gap after purge

# ── LightGBM ─────────────────────────────────────────────────────────────────
# Fixed n_estimators — no early stopping to avoid look-ahead bias.
# Conservative params: high min_child_samples and regularisation prevent
# the model from memorising noise in financial time-series.
LGBM_PARAMS = {
    "objective":         "regression",
    "metric":            "rmse",
    "n_estimators":      800,       # increased from 500 — GPU handles more trees cheaply
    "learning_rate":     0.02,
    "num_leaves":        127,       # increased from 63 — more expressive, GPU compensates speed
    "max_depth":         7,         # slightly deeper for richer interactions
    "min_child_samples": 100,
    "subsample":         0.7,
    "subsample_freq":    1,
    "colsample_bytree":  0.7,
    "reg_alpha":         0.1,
    "reg_lambda":        1.0,
    "random_state":      42,
    "verbose":          -1,
    "n_jobs":           -1,
    # GPU (OpenCL) — avoids CUDA build requirement, works with NVIDIA/AMD via OpenCL
    "device":           "gpu",
    "gpu_platform_id":   0,
    "gpu_device_id":     0,
}

# ── Ridge ─────────────────────────────────────────────────────────────────────
RIDGE_ALPHA = 1.0

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT_DIR    = Path(__file__).parent
MODELS_DIR  = ROOT_DIR / "models"
RESULTS_DIR = ROOT_DIR / "results"

MODELS_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)
