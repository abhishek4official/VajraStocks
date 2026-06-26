"""Backtest Lab API (V2.0 spec M2).

Runs the real, reproducible single-name engine over adjusted bars from the columnar data
plane, optionally persisting the result. Replaces the deleted fabricated backtester — every
number returned here is computed, never a constant.
"""

from __future__ import annotations

import datetime as dt
import math
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from stocks.api.deps import get_bar_store, get_db
from stocks.data.backfill import backfill_all, load_actions
from stocks.data.bar_store import BarStore
from stocks.db.models import Symbol
from stocks.services.quant.backtest.engine import BacktestConfig
from stocks.services.quant.backtest.persistence import BacktestRepository
from stocks.services.quant.backtest.portfolio import run_strategy_backtest
from stocks.services.quant.backtest.replay import run_symbol_backtest
from stocks.services.quant.backtest.signals import (
    breakout_signals,
    ema_crossover_signals,
    get_signal,
    list_signals,
    sma_crossover_signals,
)
from stocks.services.quant.backtest.walkforward import walk_forward
from stocks.services.strategies.registry import get_strategy

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


class WalkForwardRequest(BaseModel):
    symbol: str
    signal: str = "sma_crossover"
    param_grid: list[dict[str, Any]]
    n_splits: int = 4
    train_frac: float = 0.6
    metric: str = "sharpe_ratio"
    stop_pct: float | None = None
    target_pct: float | None = None
    adjusted: bool = False
    start: dt.date | None = None
    end: dt.date | None = None


class WindowOut(BaseModel):
    test_start: int
    test_end: int
    best_params: dict[str, Any]
    in_sample_metric: float | None
    oos: MetricsOut


class WalkForwardOut(BaseModel):
    symbol: str
    signal: str
    windows: list[WindowOut]
    avg_oos_return: float
    avg_oos_sharpe: float
    pct_profitable_windows: float


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
    if signal == "ema_crossover":
        return lambda b: ema_crossover_signals(b, **params)
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
class BackfillOut(BaseModel):
    symbols_mirrored: int
    rows: int


class PortfolioBacktestRequest(BaseModel):
    strategy_id: str
    universe: list[str]
    params: dict[str, Any] = {}
    force_market_ok: bool = True
    cost_bps: float = 0.0
    adjusted: bool = False
    start: dt.date | None = None
    end: dt.date | None = None


class PortfolioMetricsOut(BaseModel):
    total_return: float
    cagr: float
    max_drawdown: float
    sharpe_ratio: float


class PortfolioBacktestOut(BaseModel):
    strategy_id: str
    symbols: int
    bars: int
    final_equity: float
    metrics: PortfolioMetricsOut
    equity_curve: list[float]
    dates: list[str]


@router.get("/signals")
def get_signals():
    """List the registered setup signals available to backtest."""
    return {"signals": list_signals()}


@router.post("/backfill", response_model=BackfillOut)
def backfill(
    full: bool = False,
    db: Session = Depends(get_db),
    store: BarStore = Depends(get_bar_store),
):
    """Mirror the SQLite price history into the columnar BarStore so backtests have data.

    Runs incrementally by default (only symbols with new bars); ``full=true`` re-mirrors all.
    A one-time action for existing installs — afterwards each sync keeps the store current.
    """
    result = backfill_all(db, store, incremental=not full)
    return BackfillOut(symbols_mirrored=len(result), rows=sum(result.values()))


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


@router.post("/walk-forward", response_model=WalkForwardOut)
def walk_forward_endpoint(
    body: WalkForwardRequest,
    db: Session = Depends(get_db),
    store: BarStore = Depends(get_bar_store),
):
    """Anchored walk-forward: grid-search params in-sample, evaluate out-of-sample per window."""
    symbol = _normalize(body.symbol)
    if not body.param_grid:
        raise HTTPException(status_code=400, detail="param_grid must not be empty")

    actions = None
    if body.adjusted:
        symbol_id = db.scalar(select(Symbol.id).where(Symbol.symbol == symbol))
        if symbol_id is not None:
            actions = load_actions(db, symbol_id)

    bars = store.read_bars(symbol, start=body.start, end=body.end, adjusted=body.adjusted, actions=actions)

    def factory(params):
        try:
            return _build_signal_fn(body.signal, params)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    try:
        result = walk_forward(
            bars, factory, body.param_grid,
            n_splits=body.n_splits, train_frac=body.train_frac, metric=body.metric,
            stop_pct=body.stop_pct, target_pct=body.target_pct,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    return WalkForwardOut(
        symbol=symbol,
        signal=body.signal,
        windows=[
            WindowOut(
                test_start=w.test_start, test_end=w.test_end, best_params=w.best_params,
                in_sample_metric=_finite(w.in_sample_metric), oos=_metrics_out(w.oos),
            )
            for w in result.windows
        ],
        avg_oos_return=result.avg_oos_return,
        avg_oos_sharpe=result.avg_oos_sharpe,
        pct_profitable_windows=result.pct_profitable_windows,
    )


@router.post("/portfolio", response_model=PortfolioBacktestOut)
def portfolio_run(
    body: PortfolioBacktestRequest,
    db: Session = Depends(get_db),
    store: BarStore = Depends(get_bar_store),
):
    """Backtest a real swing.py strategy across a universe (weight-based portfolio engine)."""
    adapter = get_strategy(body.strategy_id)
    if adapter is None:
        raise HTTPException(status_code=404, detail=f"Unknown strategy '{body.strategy_id}'")

    frames: list[pd.DataFrame] = []
    for raw in body.universe:
        symbol = _normalize(raw)
        actions = None
        if body.adjusted:
            symbol_id = db.scalar(select(Symbol.id).where(Symbol.symbol == symbol))
            if symbol_id is not None:
                actions = load_actions(db, symbol_id)
        bars = store.read_bars(symbol, start=body.start, end=body.end, adjusted=body.adjusted, actions=actions)
        if bars.empty:
            continue
        b = bars.rename(columns={"trading_date": "date"})
        b["symbol"] = symbol
        frames.append(b[["date", "symbol", "open", "high", "low", "close", "volume"]])

    if not frames:
        raise HTTPException(status_code=400, detail="No stored bars for the requested universe")

    market_data = pd.concat(frames, ignore_index=True)
    strat = adapter.make(body.params, force_market_ok=body.force_market_ok)
    result = run_strategy_backtest(strat, market_data, config=BacktestConfig(cost_bps=body.cost_bps))

    m = result.metrics
    return PortfolioBacktestOut(
        strategy_id=body.strategy_id,
        symbols=len(frames),
        bars=len(result.equity_curve),
        final_equity=result.equity_curve[-1] if result.equity_curve else 0.0,
        metrics=PortfolioMetricsOut(
            total_return=m.total_return, cagr=m.cagr,
            max_drawdown=m.max_drawdown, sharpe_ratio=m.sharpe_ratio,
        ),
        equity_curve=result.equity_curve,
        dates=[d.isoformat() for d in result.dates],
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
