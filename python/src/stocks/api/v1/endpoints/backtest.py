"""Backtest Lab API (V2.0 spec M2).

Runs the real, reproducible single-name engine over adjusted bars from the columnar data
plane, optionally persisting the result. Replaces the deleted fabricated backtester — every
number returned here is computed, never a constant.
"""

from __future__ import annotations

import datetime as dt
import math
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from stocks.api.deps import get_bar_store, get_db
from stocks.data.backfill import load_actions
from stocks.data.bar_store import BarStore
from stocks.db.models import Symbol
from stocks.services.quant.backtest.engine import BacktestConfig
from stocks.services.quant.backtest.persistence import BacktestRepository
from stocks.services.quant.backtest.replay import run_symbol_backtest
from stocks.services.quant.backtest.signals import (
    breakout_signals,
    get_signal,
    list_signals,
    sma_crossover_signals,
)

router = APIRouter(prefix="/backtest", tags=["Backtest Lab"])


# ── Schemas ───────────────────────────────────────────────────────────────────
class BacktestRunRequest(BaseModel):
    symbol: str
    signal: str = "sma_crossover"
    params: dict[str, Any] = {}
    stop_pct: float | None = None
    target_pct: float | None = None
    cost_bps: float = 0.0
    slippage_bps: float = 0.0
    initial_capital: float = 100_000.0
    adjusted: bool = False
    start: dt.date | None = None
    end: dt.date | None = None
    save: bool = False


class MetricsOut(BaseModel):
    total_return: float
    cagr: float
    max_drawdown: float
    win_rate: float
    profit_factor: float | None  # None when undefined (no losses -> infinite)
    sharpe_ratio: float
    trades: int


class TradeOut(BaseModel):
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    qty: float
    return_pct: float
    reason: str


class BacktestRunOut(BaseModel):
    run_id: int | None
    symbol: str
    signal: str
    bars: int
    metrics: MetricsOut
    trades: list[TradeOut]


class SavedRunOut(BaseModel):
    id: int
    symbol: str
    signal: str
    trades_count: int
    created_at: str
    metrics: dict[str, float]
    trades: list[TradeOut] = []


# ── helpers ───────────────────────────────────────────────────────────────────
def _normalize(symbol: str) -> str:
    s = symbol.strip().upper()
    if not s.endswith(".NS") and not s.startswith("^"):
        s = f"{s}.NS"
    return s


def _finite(v: float) -> float | None:
    return v if math.isfinite(v) else None


def _build_signal_fn(signal: str, params: dict[str, Any]):
    params = params or {}
    if signal == "sma_crossover":
        return lambda b: sma_crossover_signals(b, **params)
    if signal == "breakout":
        return lambda b: breakout_signals(b, **params)
    return get_signal(signal)  # raises ValueError for unknown names


def _metrics_out(m) -> MetricsOut:
    return MetricsOut(
        total_return=m.total_return,
        cagr=m.cagr,
        max_drawdown=m.max_drawdown,
        win_rate=m.win_rate,
        profit_factor=_finite(m.profit_factor),
        sharpe_ratio=m.sharpe_ratio,
        trades=m.trades,
    )


def _trade_out(t) -> TradeOut:
    return TradeOut(
        entry_date=t.entry_date.isoformat(),
        entry_price=t.entry_price,
        exit_date=t.exit_date.isoformat(),
        exit_price=t.exit_price,
        qty=t.qty,
        return_pct=t.return_pct,
        reason=t.reason,
    )


# ── routes ────────────────────────────────────────────────────────────────────
@router.get("/signals")
def get_signals():
    """List the registered setup signals available to backtest."""
    return {"signals": list_signals()}


@router.post("/run", response_model=BacktestRunOut)
def run(
    body: BacktestRunRequest,
    db: Session = Depends(get_db),
    store: BarStore = Depends(get_bar_store),
):
    """Run a single-name backtest; optionally persist it."""
    symbol = _normalize(body.symbol)

    try:
        signal_fn = _build_signal_fn(body.signal, body.params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    actions = None
    if body.adjusted:
        symbol_id = db.scalar(select(Symbol.id).where(Symbol.symbol == symbol))
        if symbol_id is not None:
            actions = load_actions(db, symbol_id)

    result = run_symbol_backtest(
        store,
        symbol,
        signal_fn,
        start=body.start,
        end=body.end,
        adjusted=body.adjusted,
        actions=actions,
        stop_pct=body.stop_pct,
        target_pct=body.target_pct,
        config=BacktestConfig(
            initial_capital=body.initial_capital,
            cost_bps=body.cost_bps,
            slippage_bps=body.slippage_bps,
        ),
    )

    run_id = None
    if body.save:
        params = {
            **body.params,
            "stop_pct": body.stop_pct,
            "target_pct": body.target_pct,
            "cost_bps": body.cost_bps,
            "slippage_bps": body.slippage_bps,
            "initial_capital": body.initial_capital,
            "adjusted": body.adjusted,
        }
        run_id = BacktestRepository(db).save(
            symbol=symbol, signal=body.signal, result=result,
            params=params, start=body.start, end=body.end,
        )

    return BacktestRunOut(
        run_id=run_id,
        symbol=symbol,
        signal=body.signal,
        bars=len(result.equity_curve),
        metrics=_metrics_out(result.metrics),
        trades=[_trade_out(t) for t in result.trades],
    )


@router.get("/runs", response_model=list[SavedRunOut])
def list_runs(symbol: str | None = None, db: Session = Depends(get_db)):
    """List saved backtest runs, newest first (optionally filtered by symbol)."""
    repo = BacktestRepository(db)
    out = []
    for r in repo.list(symbol=_normalize(symbol) if symbol else None):
        out.append(SavedRunOut(
            id=r.id, symbol=r.symbol, signal=r.signal, trades_count=r.trades_count,
            created_at=r.created_at.isoformat() if r.created_at else "",
            metrics=repo.get_metrics(r.id),
        ))
    return out


@router.get("/runs/{run_id}", response_model=SavedRunOut)
def get_run(run_id: int, db: Session = Depends(get_db)):
    """Full detail for a saved run: metrics + per-trade audit trail."""
    repo = BacktestRepository(db)
    run = repo.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No backtest run {run_id}")
    return SavedRunOut(
        id=run.id, symbol=run.symbol, signal=run.signal, trades_count=run.trades_count,
        created_at=run.created_at.isoformat() if run.created_at else "",
        metrics=repo.get_metrics(run.id),
        trades=[_trade_out(t) for t in run.trades],
    )
