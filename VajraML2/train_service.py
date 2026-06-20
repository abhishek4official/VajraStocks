"""
VajraML2 background training service — triple-barrier LGBMClassifier.

Progress events (SSE-compatible JSON dicts):
  stage      — human-readable phase message
  dataset    — rows / features / date range
  fold_start — fold N/total, train/test rows and dates
  tree       — per-tree progress within a fold
  fold_done  — ic_ptp / tp_prec / hit_5d / ls_pnl per fold
  complete   — mean_ic_ptp / mean_tp_prec across all folds
  cancelled  — user-initiated stop
  error      — exception details
"""

import json
import queue
import threading
from datetime import datetime, timezone
from typing import Optional

import lightgbm as lgb
import numpy as np
from sqlalchemy import text

from VajraML2.config import (
    EMBARGO_DAYS,
    LGBM_PARAMS_V2,
    MIN_TRAIN_DAYS,
    MODELS_DIR,
    PURGE_DAYS,
    TEST_DAYS,
)


class _Cancelled(Exception):
    pass


def _emit(q: queue.Queue, event: dict) -> None:
    try:
        q.put_nowait(event)
    except queue.Full:
        pass


def _update_run(engine, run_id: int, **fields) -> None:
    if not fields:
        return
    try:
        sets = ", ".join(f"{k}=:{k}" for k in fields)
        with engine.begin() as conn:
            conn.execute(
                text(f"UPDATE ml2_training_runs SET {sets} WHERE id=:id"),
                {**fields, "id": run_id},
            )
    except Exception:
        pass


def _make_lgbm_callback(cancel_event: threading.Event, q: queue.Queue,
                        fold: int, pct_start: float, pct_end: float):
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


def train_with_progress_v2(engine, cancel_event: threading.Event,
                            progress_q: queue.Queue, run_id: int) -> None:
    """
    Full V2 walk-forward training pipeline.  Runs in a daemon thread.
    Always uses CPU (GPU OOM'd on fold 3 due to 297K+ training rows).
    """

    def emit(event: dict) -> None:
        _emit(progress_q, event)

    def update(**fields) -> None:
        _update_run(engine, run_id, **fields)

    try:
        import sys
        from pathlib import Path as _Path
        _root = str(_Path(__file__).parents[1])
        if _root not in sys.path:
            sys.path.insert(0, _root)

        # ── 1. Feature matrix + triple-barrier labels ──────────────────────────
        emit({"type": "stage", "message": "Loading prices and building features...", "pct": 3})
        from VajraML2.pipeline2 import build_training_dataset
        df, feature_cols = build_training_dataset(engine)

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

        # ── 2. Count folds ─────────────────────────────────────────────────────
        trading_dates = sorted(df["trading_date"].dt.date.unique())
        n          = len(trading_dates)
        test_start = MIN_TRAIN_DAYS + PURGE_DAYS + EMBARGO_DAYS

        total_folds, ts = 0, test_start
        while ts + TEST_DAYS <= n:
            total_folds += 1
            ts += TEST_DAYS

        emit({"type": "stage",
              "message": f"Starting walk-forward — {total_folds} folds (CPU)...",
              "pct": 12})

        results      = []
        fold         = 0
        pct_per_fold = 83.0 / max(total_folds, 1)

        # ── 3. Walk-forward loop ───────────────────────────────────────────────
        while test_start + TEST_DAYS <= n:
            fold += 1
            if cancel_event.is_set():
                raise _Cancelled()

            train_end   = test_start - PURGE_DAYS - EMBARGO_DAYS
            test_end    = min(test_start + TEST_DAYS, n)
            train_dates = set(trading_dates[:train_end])
            test_dates  = set(trading_dates[test_start:test_end])

            train = df[df["trading_date"].dt.date.isin(train_dates)].dropna(
                subset=["tb_label_enc", "fwd_ret_5d"]
            )
            test = df[df["trading_date"].dt.date.isin(test_dates)].dropna(
                subset=["tb_label_enc", "fwd_ret_5d"]
            )

            if len(train) < 1_000 or len(test) < 100:
                test_start += TEST_DAYS
                continue

            pct_start    = 12 + (fold - 1) * pct_per_fold
            pct_lgbm_end = pct_start + pct_per_fold * 0.95
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
            y_train = train["tb_label_enc"].astype(int)
            X_test  = test[feature_cols]
            tb_test = test["tb_label"].values
            raw_ret = test["fwd_ret_5d"].values

            cb         = _make_lgbm_callback(cancel_event, progress_q, fold, pct_start, pct_lgbm_end)
            lgbm_model = lgb.LGBMClassifier(**LGBM_PARAMS_V2)
            lgbm_model.fit(X_train, y_train, callbacks=[cb])
            proba      = lgbm_model.predict_proba(X_test)   # (n, 3)

            # Save fold model + feature list
            fold_dir = MODELS_DIR / f"fold_{fold:02d}"
            fold_dir.mkdir(exist_ok=True)
            lgbm_path = fold_dir / "lgbm_v2.txt"
            lgbm_model.booster_.save_model(str(lgbm_path))
            lgbm_path.write_bytes(lgbm_path.read_bytes().replace(b"\r\n", b"\n"))
            (fold_dir / "feature_cols.json").write_text(json.dumps(feature_cols))

            # Evaluate
            from VajraML2.evaluate import evaluate_fold_v2
            result = evaluate_fold_v2(
                fold=fold,
                test_df=test,
                proba=proba,
                tb_label=tb_test,
                raw_ret=raw_ret,
                feature_cols=feature_cols,
                lgbm_model=lgbm_model,
            )
            results.append(result)

            emit({
                "type":     "fold_done",
                "fold":     fold,
                "total":    total_folds,
                "ic_ptp":   round(float(result.get("ic_tp",    0)), 4),
                "tp_prec":  round(float(result.get("tp_prec",  0)) * 100, 1),
                "hit_5d":   round(float(result.get("hit_5d",   0)) * 100, 1),
                "ls_pnl":   round(float(result.get("ls_return",0)) * 100, 2),
                "pct":      int(pct_end),
            })

            test_start += TEST_DAYS

        # ── 4. Final production model on ALL data ──────────────────────────────
        emit({"type": "stage",
              "message": "Training final production model on all data...",
              "pct": 96})
        final_df = df.dropna(subset=["tb_label_enc", "fwd_ret_5d"])
        if len(final_df) >= 1_000 and not cancel_event.is_set():
            X_ft = final_df[feature_cols]
            y_ft = final_df["tb_label_enc"].astype(int)
            cb_ft = _make_lgbm_callback(cancel_event, progress_q, 0, 96, 99)
            lgbm_final = lgb.LGBMClassifier(**LGBM_PARAMS_V2)
            lgbm_final.fit(X_ft, y_ft, callbacks=[cb_ft])

            final_dir = MODELS_DIR / "fold_final"
            final_dir.mkdir(exist_ok=True)
            lgbm_path_f = final_dir / "lgbm_v2.txt"
            lgbm_final.booster_.save_model(str(lgbm_path_f))
            lgbm_path_f.write_bytes(lgbm_path_f.read_bytes().replace(b"\r\n", b"\n"))
            (final_dir / "feature_cols.json").write_text(json.dumps(feature_cols))

        # ── 5. Finalise ────────────────────────────────────────────────────────
        mean_ic_ptp  = float(np.mean([r.get("ic_tp",   0) for r in results]))
        mean_tp_prec = float(np.mean([r.get("tp_prec", 0) for r in results]))
        fold_metrics = json.dumps([
            {
                "fold":     r["fold"],
                "ic_ptp":   round(float(r.get("ic_tp",    0)), 4),
                "tp_prec":  round(float(r.get("tp_prec",  0)) * 100, 1),
                "hit_5d":   round(float(r.get("hit_5d",   0)) * 100, 1),
                "ls_pnl":   round(float(r.get("ls_return",0)) * 100, 2),
            }
            for r in results
        ])
        update(
            status="COMPLETED",
            completed_at=datetime.now(timezone.utc),
            num_folds=fold,
            mean_ic_ptp=round(mean_ic_ptp, 4),
            fold_metrics=fold_metrics,
        )
        emit({
            "type":         "complete",
            "mean_ic_ptp":  round(mean_ic_ptp, 4),
            "mean_tp_prec": round(mean_tp_prec * 100, 1),
            "folds":        fold,
            "pct":          100,
        })

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
        progress_q.put(None)


class TrainingJob:
    __slots__ = ("thread", "cancel_event", "progress_q", "run_id", "started_at")

    def __init__(self, thread: threading.Thread, cancel_event: threading.Event,
                 progress_q: queue.Queue, run_id: int) -> None:
        self.thread       = thread
        self.cancel_event = cancel_event
        self.progress_q   = progress_q
        self.run_id       = run_id
        self.started_at   = datetime.now(timezone.utc)


class TrainingJobManagerV2:
    """Thread-safe singleton for V2 training jobs."""

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
                raise RuntimeError("A V2 training job is already running.")
            cancel_event = threading.Event()
            progress_q   = queue.Queue(maxsize=5000)
            thread = threading.Thread(
                target=train_with_progress_v2,
                args=(engine, cancel_event, progress_q, run_id),
                name="vajraml2-train",
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
