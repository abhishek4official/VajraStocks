"""
Background training service with progress reporting and cancellation support.

Provides:
  detect_device()       — GPU probe (OpenCL via LightGBM); falls back to CPU
  TrainingJobManager    — thread-safe singleton; owns the background thread + queue
  train_with_progress() — background function; writes JSON events to a Queue
"""

import json
import pickle
import queue
import threading
from datetime import datetime, timezone
from typing import Optional

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import mstats
from sklearn.linear_model import Ridge
from sklearn.preprocessing import RobustScaler
from sqlalchemy import text

from VajraML.config import (
    EMBARGO_DAYS,
    LGBM_PARAMS,
    MIN_TRAIN_DAYS,
    MODELS_DIR,
    PURGE_DAYS,
    RIDGE_ALPHA,
    TEST_DAYS,
)
from VajraML.evaluate import evaluate_fold
from VajraML.pipeline import build_dataset


# ── Hardware detection ─────────────────────────────────────────────────────────

def detect_device() -> str:
    """
    Probe LightGBM GPU support by running a tiny 2-tree fit.
    Returns 'gpu' if OpenCL is available, 'cpu' otherwise.
    Falls back silently — never raises.
    """
    try:
        rng   = np.random.default_rng(0)
        probe = lgb.LGBMRegressor(
            n_estimators=2, num_leaves=4,
            device="gpu", gpu_platform_id=0, gpu_device_id=0,
            verbose=-1,
        )
        probe.fit(rng.random((50, 5)), rng.random(50))
        return "gpu"
    except Exception:
        return "cpu"


def _build_params(device: str) -> dict:
    params = dict(LGBM_PARAMS)
    if device == "cpu":
        params.pop("device", None)
        params.pop("gpu_platform_id", None)
        params.pop("gpu_device_id", None)
    return params


# ── Cancellation ───────────────────────────────────────────────────────────────

class _Cancelled(Exception):
    pass


# ── Progress helpers ───────────────────────────────────────────────────────────

def _emit(q: queue.Queue, event: dict) -> None:
    try:
        q.put_nowait(event)
    except queue.Full:
        pass  # never block training; drop if consumer is slow


def _make_lgbm_callback(cancel_event: threading.Event, q: queue.Queue,
                         fold: int, pct_start: float, pct_end: float):
    """LightGBM callback: reports per-tree progress and checks for cancellation."""

    def cb(env):
        if cancel_event.is_set():
            raise _Cancelled()
        tree  = env.iteration + 1
        total = env.end_iteration or 1
        pct   = pct_start + (pct_end - pct_start) * (tree / total)
        _emit(q, {"type": "tree", "fold": fold, "tree": tree, "total": total, "pct": int(pct)})

    cb.order            = 10
    cb.before_iteration = False
    return cb


# ── DB helper ──────────────────────────────────────────────────────────────────

def _update_run(engine, run_id: int, **fields) -> None:
    if not fields:
        return
    try:
        sets = ", ".join(f"{k}=:{k}" for k in fields)
        with engine.begin() as conn:
            conn.execute(
                text(f"UPDATE ml_training_runs SET {sets} WHERE id=:id"),
                {**fields, "id": run_id},
            )
    except Exception:
        pass  # don't mask primary training errors


# ── Background training function ───────────────────────────────────────────────

def train_with_progress(engine, cancel_event: threading.Event,
                        progress_q: queue.Queue, run_id: int) -> None:
    """
    Full walk-forward training pipeline.  Runs in a daemon thread.

    Emits structured JSON dicts to progress_q throughout.
    Always terminates by pushing None (sentinel) so the SSE stream knows to close.
    Updates ml_training_runs.status in the DB on every terminal state change.
    """

    def emit(event: dict) -> None:
        _emit(progress_q, event)

    def update(**fields) -> None:
        _update_run(engine, run_id, **fields)

    try:
        # ── 1. Hardware detection ──────────────────────────────────────────────
        emit({"type": "stage", "message": "Detecting hardware...", "pct": 1})
        device = detect_device()
        params = _build_params(device)
        emit({"type": "device", "device": device, "pct": 2})
        update(device=device)

        # ── 2. Feature matrix ──────────────────────────────────────────────────
        emit({"type": "stage", "message": "Loading prices and building features...", "pct": 3})
        df, feature_cols = build_dataset(engine)

        n_rows   = len(df)
        date_min = df["trading_date"].min().date()
        date_max = df["trading_date"].max().date()
        emit({
            "type":       "dataset",
            "rows":       n_rows,
            "features":   len(feature_cols),
            "date_start": date_min.isoformat(),
            "date_end":   date_max.isoformat(),
            "pct":        10,
        })
        update(dataset_rows=n_rows, date_range_start=date_min, date_range_end=date_max)

        if cancel_event.is_set():
            raise _Cancelled()

        # ── 3. Count folds ─────────────────────────────────────────────────────
        trading_dates = sorted(df["trading_date"].dt.date.unique())
        n          = len(trading_dates)
        test_start = MIN_TRAIN_DAYS + PURGE_DAYS + EMBARGO_DAYS

        total_folds, ts = 0, test_start
        while ts + TEST_DAYS <= n:
            total_folds += 1
            ts += TEST_DAYS

        emit({"type": "stage",
              "message": f"Starting walk-forward training — {total_folds} folds...",
              "pct": 12})

        results      = []
        fold         = 0
        pct_per_fold = 83.0 / max(total_folds, 1)

        # ── 4. Walk-forward loop ───────────────────────────────────────────────
        while test_start + TEST_DAYS <= n:
            fold += 1
            if cancel_event.is_set():
                raise _Cancelled()

            train_end   = test_start - PURGE_DAYS - EMBARGO_DAYS
            test_end    = min(test_start + TEST_DAYS, n)
            train_dates = set(trading_dates[:train_end])
            test_dates  = set(trading_dates[test_start:test_end])

            train = df[df["trading_date"].dt.date.isin(train_dates)].dropna(
                subset=["fwd_ret_vol_adj", "fwd_ret_5d"]
            )
            test = df[df["trading_date"].dt.date.isin(test_dates)].dropna(
                subset=["fwd_ret_vol_adj", "fwd_ret_5d"]
            )

            if len(train) < 1_000 or len(test) < 100:
                test_start += TEST_DAYS
                continue

            pct_start    = 12 + (fold - 1) * pct_per_fold
            pct_lgbm_end = pct_start + pct_per_fold * 0.75
            pct_end      = pct_start + pct_per_fold

            emit({
                "type":            "fold_start",
                "fold":            fold,
                "total":           total_folds,
                "train_rows":      len(train),
                "test_rows":       len(test),
                "date_start":      str(min(train_dates)),
                "date_end":        str(max(train_dates)),
                "test_date_start": str(min(test_dates)),
                "test_date_end":   str(max(test_dates)),
                "pct":             int(pct_start),
            })

            X_train = train[feature_cols]
            y_train = train["fwd_ret_vol_adj"]
            X_test  = test[feature_cols]
            y_test  = test["fwd_ret_vol_adj"]

            y_win = pd.Series(
                mstats.winsorize(y_train.values, limits=[0.01, 0.01]),
                index=y_train.index,
            )

            # LightGBM
            cb         = _make_lgbm_callback(cancel_event, progress_q, fold, pct_start, pct_lgbm_end)
            lgbm_model = lgb.LGBMRegressor(**params)
            lgbm_model.fit(X_train, y_win, callbacks=[cb])
            lgbm_pred  = lgbm_model.predict(X_test)

            # Ridge
            emit({"type": "stage",
                  "message": f"Fold {fold}/{total_folds}: Ridge regression...",
                  "pct": int(pct_lgbm_end)})
            scaler      = RobustScaler()
            X_train_s   = scaler.fit_transform(X_train.fillna(0))
            X_test_s    = scaler.transform(X_test.fillna(0))
            ridge_model = Ridge(alpha=RIDGE_ALPHA)
            ridge_model.fit(X_train_s, y_win)
            ridge_pred  = ridge_model.predict(X_test_s)

            # Persist models
            fold_dir = MODELS_DIR / f"fold_{fold:02d}"
            fold_dir.mkdir(exist_ok=True)
            lgbm_model.booster_.save_model(str(fold_dir / "lgbm.txt"))
            with open(fold_dir / "ridge.pkl", "wb") as fh:
                pickle.dump({"model": ridge_model, "scaler": scaler}, fh)

            # Evaluate
            result = evaluate_fold(
                fold=fold,
                test_df=test,
                lgbm_pred=lgbm_pred,
                ridge_pred=ridge_pred,
                y_true_vol_adj=y_test.values,
                y_true_raw=test["fwd_ret_5d"].values,
                feature_cols=feature_cols,
                lgbm_model=lgbm_model,
            )
            results.append(result)

            emit({
                "type":     "fold_done",
                "fold":     fold,
                "total":    total_folds,
                "lgbm_ic":  round(float(result.get("lgbm_ic",  0)), 4),
                "ridge_ic": round(float(result.get("ridge_ic", 0)), 4),
                "hit_rate": round(float(result.get("lgbm_hit", 0)) * 100, 1),
                "ls_pnl":   round(float(result.get("ls_lgbm",  0)) * 100, 2),
                "pct":      int(pct_end),
            })

            test_start += TEST_DAYS

        # ── 5. Finalise ────────────────────────────────────────────────────────
        mean_ic = float(np.mean([r.get("lgbm_ic", 0) for r in results]))
        fold_metrics = json.dumps([
            {
                "fold":     r["fold"],
                "lgbm_ic":  round(float(r.get("lgbm_ic",  0)), 4),
                "ridge_ic": round(float(r.get("ridge_ic", 0)), 4),
                "hit_rate": round(float(r.get("lgbm_hit", 0)) * 100, 1),
                "ls_pnl":   round(float(r.get("ls_lgbm",  0)) * 100, 2),
            }
            for r in results
        ])
        update(
            status="COMPLETED",
            completed_at=datetime.now(timezone.utc),
            num_folds=fold,
            mean_ic=round(mean_ic, 4),
            fold_metrics=fold_metrics,
        )
        emit({"type": "complete", "mean_ic": round(mean_ic, 4), "folds": fold, "pct": 100})

    except _Cancelled:
        update(status="CANCELLED", completed_at=datetime.now(timezone.utc))
        emit({"type": "cancelled", "pct": 0})

    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        update(status="FAILED", completed_at=datetime.now(timezone.utc),
               error_message=str(exc)[:2000])
        emit({"type": "error", "message": str(exc), "traceback": tb[:1000], "pct": 0})

    finally:
        progress_q.put(None)  # sentinel — SSE generator exits on None


# ── Job manager ────────────────────────────────────────────────────────────────

class TrainingJob:
    __slots__ = ("thread", "cancel_event", "progress_q", "run_id", "started_at")

    def __init__(self, thread: threading.Thread, cancel_event: threading.Event,
                 progress_q: queue.Queue, run_id: int) -> None:
        self.thread       = thread
        self.cancel_event = cancel_event
        self.progress_q   = progress_q
        self.run_id       = run_id
        self.started_at   = datetime.now(timezone.utc)


class TrainingJobManager:
    """
    Thread-safe singleton that owns exactly one background training job at a time.

    Attach to app.state.training_manager in FastAPI lifespan so all request
    handlers share the same instance.
    """

    def __init__(self) -> None:
        self._lock: threading.Lock       = threading.Lock()
        self._job:  Optional[TrainingJob] = None

    def is_running(self) -> bool:
        with self._lock:
            return self._job is not None and self._job.thread.is_alive()

    def current_run_id(self) -> Optional[int]:
        with self._lock:
            return self._job.run_id if self._job else None

    def current_job(self) -> Optional[TrainingJob]:
        with self._lock:
            return self._job

    def start(self, engine, run_id: int) -> TrainingJob:
        with self._lock:
            if self._job is not None and self._job.thread.is_alive():
                raise RuntimeError("A training job is already running.")
            cancel_event = threading.Event()
            progress_q   = queue.Queue(maxsize=5000)
            thread = threading.Thread(
                target=train_with_progress,
                args=(engine, cancel_event, progress_q, run_id),
                name="vajraml-train",
                daemon=True,
            )
            self._job = TrainingJob(thread, cancel_event, progress_q, run_id)
            thread.start()
            return self._job

    def cancel(self) -> bool:
        with self._lock:
            if self._job and self._job.thread.is_alive():
                self._job.cancel_event.set()
                return True
            return False
