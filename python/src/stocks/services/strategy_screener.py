"""Materializer for strategy signals — the post-sync layer behind the Strategy screen.

Runs the research-backed swing/position strategies (`strategies/swing.py`) on WEEKLY
bars (resampled from stored daily OHLCV) across the active universe and stores one
``StrategySignal`` row per (symbol, strategy). The screen reads that table so it never
does live computation.

Performance design (load-once / compute-all / bulk-write):
  * The entire daily-price history is read in ONE query and resampled to weekly ONCE
    per run (`_build_weekly_cache`); the cache is reused across every strategy — no
    per-symbol, per-strategy reloads.
  * Each strategy is written with a single set-based ``DELETE`` + ``bulk_insert_mappings``
    (no per-row SELECT/UPDATE round-trips).
  * Orphaned strategy ids (e.g. a retired strategy) are purged in the same pass.

Signal mapping (per symbol, latest weekly bar):
  * eligible & market risk-on (or forced) → BUY
  * eligible & market risk-off            → WATCH   (entry blocked by regime)
  * hold_ok  & not eligible               → WATCH   (still in an uptrend)
  * held but thesis broken                → SELL
  * otherwise                             → NONE
A cross-sectional percentile of the strategy's leadership score becomes the 0-100
`score`, so the screen can rank leaders even when few names are eligible.
"""

from __future__ import annotations

import datetime as dt
import json

import numpy as np
import pandas as pd
from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from stocks.config import Config
from stocks.db.models import DailyPrice, PortfolioHolding, StrategySignal, Symbol
from stocks.services.settings_service import SettingsService
from stocks.services.strategies.registry import DEFAULT_STRATEGY_ID, get_strategy, list_strategies

_WEEKLY_RULE = "W-FRI"
_AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


class StrategyScreenerService:
    """Computes and persists materialized swing-strategy signals for the universe."""

    def __init__(self, config: Config, db_session: Session):
        self.config = config
        self.db = db_session

    def _benchmark_symbol(self) -> str:
        return SettingsService(self.db).get_str("MARKET", "rs_benchmark_symbol", "^NSEI")

    # ── data loading (ONCE per run) ───────────────────────────────────────────
    def _build_weekly_cache(self) -> tuple[dict[int, pd.DataFrame], dict[int, Symbol], pd.Series | None]:
        """One bulk read of all daily OHLCV → per-symbol weekly frames + benchmark close.

        Returns (cache{symbol_id: weekly_df}, sym_map{symbol_id: Symbol}, benchmark_close).
        """
        symbols = self.db.scalars(select(Symbol).filter_by(is_active=True)).all()
        sym_map = {s.id: s for s in symbols if not s.symbol.startswith("^")}
        bench = next((s for s in symbols if s.symbol == self._benchmark_symbol()), None)
        wanted = set(sym_map) | ({bench.id} if bench else set())
        if not wanted:
            return {}, sym_map, None

        stmt = (
            select(
                DailyPrice.symbol_id, DailyPrice.trading_date, DailyPrice.open,
                DailyPrice.high, DailyPrice.low, DailyPrice.close, DailyPrice.volume,
            )
            .where(DailyPrice.granularity == "1d")
            .order_by(DailyPrice.symbol_id, DailyPrice.trading_date)
        )
        raw = pd.read_sql(stmt, self.db.get_bind())
        if raw.empty:
            return {}, sym_map, None
        raw = raw[raw["symbol_id"].isin(wanted)]
        raw["trading_date"] = pd.to_datetime(raw["trading_date"])
        for col in ("open", "high", "low", "close", "volume"):
            raw[col] = raw[col].astype(float)

        cache: dict[int, pd.DataFrame] = {}
        for sid, g in raw.groupby("symbol_id"):
            gg = g.set_index("trading_date")[["open", "high", "low", "close", "volume"]]
            wk = gg.resample(_WEEKLY_RULE).agg(_AGG).dropna()
            if wk.empty:
                continue
            wk = wk.reset_index().rename(columns={"trading_date": "date"})
            wk["symbol"] = sym_map[sid].symbol if sid in sym_map else self._benchmark_symbol()
            cache[int(sid)] = wk

        bench_close = None
        if bench is not None and bench.id in cache:
            bwk = cache[bench.id]
            bench_close = pd.Series(bwk["close"].values, index=pd.to_datetime(bwk["date"].values))
        return cache, sym_map, bench_close

    # ── per-strategy signal rows over the cached frames ───────────────────────
    def _signals_for_strategy(
        self, strategy_id: str, cache: dict[int, pd.DataFrame], sym_map: dict[int, Symbol],
        bench_close: pd.Series | None, holdings: dict[str, float],
        force_market_ok: bool, params: dict | None,
    ) -> list[dict]:
        adapter = get_strategy(strategy_id)
        if adapter is None:
            return []
        strat = adapter.make(params, force_market_ok=force_market_ok)
        strat.parameters["timeframe"] = "weekly"
        strat.parameters["benchmark_symbol"] = self._benchmark_symbol()
        strat._bench_close = bench_close if bench_close is not None else pd.Series(dtype=float)

        risk_on = True
        if strat.parameters.get("use_market_filter", True) and bench_close is not None and len(bench_close) > 2:
            ma = bench_close.rolling(strat._bd(strat.parameters["regime_ma_days"])).mean()
            try:
                risk_on = bool(bench_close.iloc[-1] > ma.iloc[-1] and ma.iloc[-1] > ma.iloc[-2])
            except (IndexError, TypeError):
                risk_on = False

        min_bars = adapter.data_needs.get("min_bars", 60)
        stop_k = float(strat.parameters.get("stop_atr_mult", 3.0))
        profit_R = float(strat.parameters.get("profit_target_R", 0) or 0)
        now = dt.datetime.now()

        staged: list[tuple[dict, float]] = []
        for sid, wk in cache.items():
            sym = sym_map.get(sid)
            if sym is None or len(wk) < min_bars:
                continue
            try:
                last = strat._features(wk).iloc[-1]
            except Exception as e:
                logger.debug(f"[{sym.symbol}] {strategy_id} feature calc failed: {e}")
                continue

            close = float(last["close"])
            atr_v = float(last["atr"]) if not pd.isna(last["atr"]) else 0.0
            eligible = bool(last.get("eligible", False))
            hold_ok = bool(last.get("hold_ok", False))
            raw_score = float(last["score"]) if not pd.isna(last["score"]) else float("nan")

            if eligible:
                signal = "BUY" if risk_on else "WATCH"
            elif hold_ok:
                signal = "WATCH"
            else:
                signal = "NONE"
            holding_qty = holdings.get(sym.symbol.replace(".NS", "").upper(), holdings.get(sym.symbol.upper(), 0.0))
            if holding_qty and holding_qty > 0 and not hold_ok:
                signal = "SELL"

            entry = stop = target = risk_pct = None
            if signal in ("BUY", "WATCH") and atr_v > 0 and close > 0:
                entry = round(close, 2)
                stop = round(close - stop_k * atr_v, 2)
                if stop < entry:
                    risk_pct = round((entry - stop) / entry, 4)
                    if profit_R:
                        target = round(entry + profit_R * stop_k * atr_v, 2)

            row = {
                "symbol_id": sid, "symbol": sym.symbol, "company_name": sym.company_name,
                "strategy_id": strategy_id, "as_of": pd.Timestamp(last["date"]).date(),
                "signal": signal, "score": 0.0, "last_close": round(close, 2),
                "entry_ref": entry, "initial_stop": stop, "target": target,
                "risk_pct": risk_pct, "rr": None,
                "key_metrics": json.dumps({
                    "leadership": round(raw_score, 4) if np.isfinite(raw_score) else None,
                    "atr_pct": round(float(last["atr_pct"]) * 100, 2) if not pd.isna(last["atr_pct"]) else None,
                }),
                "gates": json.dumps({"eligible": eligible, "hold_ok": hold_ok}),
                "reasons": json.dumps([
                    f"{adapter.name}: {'eligible entry' if eligible else ('in uptrend (hold)' if hold_ok else 'no setup')}",
                    f"market risk_on={risk_on}",
                ]),
                "updated_at": now,
            }
            staged.append((row, raw_score))

        # Cross-sectional percentile → 0-100 leadership score.
        finite = np.array([s for _, s in staged if np.isfinite(s)], dtype=float)
        if finite.size:
            sorted_vals = np.sort(finite)
            pct = {s: float((sorted_vals <= s).mean() * 100.0) for s in set(finite.tolist())}
            for row, raw in staged:
                if np.isfinite(raw):
                    row["score"] = round(pct[raw], 1)
        logger.info(
            f"Strategy '{strategy_id}' (weekly) risk_on={risk_on}"
            f"{' (forced)' if force_market_ok else ''} → {len(staged)} rows."
        )
        return [row for row, _ in staged]

    # ── shared materialization core ───────────────────────────────────────────
    def _materialize(
        self, strategy_ids: list[str], force_market_ok: bool = False,
        params: dict | None = None, purge_orphans: bool = True,
    ) -> dict[str, int]:
        cache, sym_map, bench_close = self._build_weekly_cache()
        if not cache:
            logger.warning("No weekly data available; skipping strategy materialization.")
            return {}
        holdings = {h.instrument.upper(): float(h.qty) for h in self.db.scalars(select(PortfolioHolding)).all()}

        counts: dict[str, int] = {}
        for sid in strategy_ids:
            rows = self._signals_for_strategy(sid, cache, sym_map, bench_close, holdings, force_market_ok, params)
            # Bulk replace: one set-based delete + one bulk insert (no per-row round-trips).
            self.db.execute(delete(StrategySignal).where(StrategySignal.strategy_id == sid))
            if rows:
                self.db.bulk_insert_mappings(StrategySignal, rows)
            counts[sid] = len(rows)

        if purge_orphans:
            registered = [a.id for a in list_strategies()]
            self.db.execute(delete(StrategySignal).where(StrategySignal.strategy_id.notin_(registered)))

        self.db.commit()
        logger.info(f"Materialized strategy signals: {counts}")
        return counts

    # ── public entry points ───────────────────────────────────────────────────
    def refresh_all_strategies(self, force_market_ok: bool = False) -> dict[str, int]:
        """Rebuild signals for ALL registered strategies in a single load-once pass."""
        return self._materialize([a.id for a in list_strategies()], force_market_ok=force_market_ok)

    def refresh_all_signals(
        self, strategy_id: str = DEFAULT_STRATEGY_ID, params: dict | None = None,
        force_market_ok: bool = False,
    ) -> int:
        """Rebuild signals for a single strategy (UI Recompute with optional custom params)."""
        if get_strategy(strategy_id) is None:
            logger.warning(f"Unknown strategy '{strategy_id}'; nothing to materialize.")
            return 0
        counts = self._materialize([strategy_id], force_market_ok=force_market_ok, params=params, purge_orphans=False)
        return counts.get(strategy_id, 0)
