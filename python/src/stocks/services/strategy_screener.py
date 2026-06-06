"""Materializer for strategy signals — the post-sync layer behind the Strategy screen.

Runs the research-backed swing/position strategies (`strategies/swing.py`) on
WEEKLY bars (resampled from stored daily OHLCV) across the active universe, and
upserts one ``StrategySignal`` row per (symbol, strategy). The screen reads that
table so it never does live computation.

Signal mapping (per symbol, latest weekly bar):
  * eligible  &  market risk-on (or forced)  → BUY
  * eligible  &  market risk-off             → WATCH   (entry blocked by regime)
  * hold_ok   &  not eligible                → WATCH   (still in an uptrend)
  * otherwise                                → NONE
A cross-sectional percentile of the strategy's leadership score becomes the 0-100
`score`, so the screen can rank leaders even when few names are eligible.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from stocks.config import Config
from stocks.db.models import DailyPrice, PortfolioHolding, StrategySignal, Symbol
from stocks.services.settings_service import SettingsService
from stocks.services.strategies.registry import DEFAULT_STRATEGY_ID, get_strategy

_WEEKLY_RULE = "W-FRI"
_AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


class StrategyScreenerService:
    """Computes and persists materialized swing-strategy signals for the universe."""

    def __init__(self, config: Config, db_session: Session):
        self.config = config
        self.db = db_session

    def _benchmark_symbol(self) -> str:
        return SettingsService(self.db).get_str("MARKET", "rs_benchmark_symbol", "^NSEI")

    # ── data loading ──────────────────────────────────────────────────────────
    def _weekly_df(self, symbol_id: int, symbol: str) -> pd.DataFrame:
        """Daily OHLCV → weekly (W-FRI) frame with date/symbol columns."""
        rows = self.db.execute(
            select(
                DailyPrice.trading_date, DailyPrice.open, DailyPrice.high,
                DailyPrice.low, DailyPrice.close, DailyPrice.volume,
            )
            .where(DailyPrice.symbol_id == symbol_id, DailyPrice.granularity == "1d")
            .order_by(DailyPrice.trading_date.asc())
        ).all()
        if not rows:
            return pd.DataFrame()
        daily = pd.DataFrame(
            {
                "open": [float(r.open) for r in rows],
                "high": [float(r.high) for r in rows],
                "low": [float(r.low) for r in rows],
                "close": [float(r.close) for r in rows],
                "volume": [float(r.volume) for r in rows],
            },
            index=pd.to_datetime([r.trading_date for r in rows]),
        )
        wk = daily.resample(_WEEKLY_RULE).agg(_AGG).dropna()
        if wk.empty:
            return wk
        wk = wk.reset_index().rename(columns={"index": "date", "trading_date": "date"})
        wk.columns = ["date", "open", "high", "low", "close", "volume"]
        wk["symbol"] = symbol
        return wk

    def _weekly_benchmark_close(self) -> pd.Series | None:
        bench = self.db.scalar(select(Symbol).where(Symbol.symbol == self._benchmark_symbol()))
        if bench is None:
            return None
        wk = self._weekly_df(bench.id, bench.symbol)
        if wk.empty:
            return None
        return pd.Series(wk["close"].values, index=pd.to_datetime(wk["date"].values))

    # ── upsert ────────────────────────────────────────────────────────────────
    def _upsert(self, symbol_obj: Symbol, strategy_id: str, payload: dict) -> None:
        existing = self.db.scalar(
            select(StrategySignal).filter_by(symbol_id=symbol_obj.id, strategy_id=strategy_id)
        )
        fields = {
            "symbol": symbol_obj.symbol, "company_name": symbol_obj.company_name,
            "strategy_id": strategy_id, **payload,
        }
        if existing is None:
            self.db.add(StrategySignal(symbol_id=symbol_obj.id, **fields))
        else:
            for k, v in fields.items():
                setattr(existing, k, v)

    # ── universe-wide refresh ─────────────────────────────────────────────────
    def refresh_all_signals(
        self, strategy_id: str = DEFAULT_STRATEGY_ID, params: dict | None = None,
        force_market_ok: bool = False,
    ) -> int:
        """Rebuild signals for the whole active equity universe in one bulk commit.

        ``force_market_ok`` disables the strategy's index-regime gate so BUY entries
        fire regardless of the market trend (testing / corrective tapes).
        """
        adapter = get_strategy(strategy_id)
        if adapter is None:
            logger.warning(f"Unknown strategy '{strategy_id}'; nothing to materialize.")
            return 0

        strat = adapter.make(params, force_market_ok=force_market_ok)
        strat.parameters["timeframe"] = "weekly"
        strat.parameters["benchmark_symbol"] = self._benchmark_symbol()

        bench_close = self._weekly_benchmark_close()
        strat._bench_close = bench_close if bench_close is not None else pd.Series(dtype=float)

        # Market regime (latest weekly bar) — forced True when the gate is off.
        risk_on = True
        if strat.parameters.get("use_market_filter", True) and bench_close is not None and len(bench_close) > 2:
            ma = bench_close.rolling(strat._bd(strat.parameters["regime_ma_days"])).mean()
            try:
                risk_on = bool(bench_close.iloc[-1] > ma.iloc[-1] and ma.iloc[-1] > ma.iloc[-2])
            except (IndexError, TypeError):
                risk_on = False
        logger.info(
            f"Materializing '{strategy_id}' (weekly) — risk_on={risk_on}"
            f"{' (forced)' if force_market_ok else ''}."
        )

        holdings = {h.instrument.upper(): float(h.qty) for h in self.db.scalars(select(PortfolioHolding)).all()}
        min_bars = adapter.data_needs.get("min_bars", 60)
        stop_k = float(strat.parameters.get("stop_atr_mult", 3.0))
        profit_R = float(strat.parameters.get("profit_target_R", 0) or 0)

        # Pass 1 — per-symbol features → staged payloads + raw leadership scores.
        staged: list[tuple[Symbol, dict, float]] = []
        active = self.db.scalars(select(Symbol).filter_by(is_active=True)).all()
        for sym in active:
            if sym.symbol.startswith("^"):
                continue
            try:
                wk = self._weekly_df(sym.id, sym.symbol)
                if wk.empty or len(wk) < min_bars:
                    continue
                feat = strat._features(wk.sort_values("date").reset_index(drop=True))
                last = feat.iloc[-1]
            except Exception as e:
                logger.debug(f"[{sym.symbol}] feature calc failed: {e}")
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
                signal = "SELL"  # held but the trend thesis is broken → exit

            entry = stop = target = risk_pct = None
            if signal in ("BUY", "WATCH") and atr_v > 0 and close > 0:
                entry = round(close, 2)
                stop = round(close - stop_k * atr_v, 2)
                if stop < entry:
                    risk_pct = round((entry - stop) / entry, 4)
                    if profit_R:
                        target = round(entry + profit_R * stop_k * atr_v, 2)

            payload = dict(  # noqa: C408 — kwargs form is clearer for this wide record
                as_of=pd.Timestamp(last["date"]).date(),
                signal=signal, score=0.0, last_close=round(close, 2),
                entry_ref=entry, initial_stop=stop, target=target, risk_pct=risk_pct, rr=None,
                key_metrics=json.dumps({
                    "leadership": round(raw_score, 4) if np.isfinite(raw_score) else None,
                    "atr_pct": round(float(last["atr_pct"]) * 100, 2) if not pd.isna(last["atr_pct"]) else None,
                }),
                gates=json.dumps({"eligible": eligible, "hold_ok": hold_ok}),
                reasons=json.dumps([
                    f"{adapter.name}: {'eligible entry' if eligible else ('in uptrend (hold)' if hold_ok else 'no setup')}",
                    f"market risk_on={risk_on}",
                ]),
            )
            staged.append((sym, payload, raw_score))

        # Pass 2 — cross-sectional percentile → 0-100 leadership score, then bulk upsert.
        finite = np.array([s for _, _, s in staged if np.isfinite(s)], dtype=float)
        rank_lookup: dict[float, float] = {}
        if finite.size:
            sorted_vals = np.sort(finite)
            for s in set(finite.tolist()):
                rank_lookup[s] = float((sorted_vals <= s).mean() * 100.0)  # % of names <= s

        written = 0
        for sym, payload, raw in staged:
            if np.isfinite(raw) and raw in rank_lookup:
                payload["score"] = round(rank_lookup[raw], 1)
            self._upsert(sym, strategy_id, payload)
            written += 1

        self.db.commit()
        logger.info(f"Materialized {written} '{strategy_id}' strategy signals.")
        return written
