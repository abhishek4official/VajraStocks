"""Strategy Screener API — reads the materialized strategy_signals layer.

The screen depends only on the registry + this endpoint, never on a specific strategy
(§3, §7.1). Adding a strategy = register it; this endpoint surfaces it automatically.
"""

import json

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from stocks.api.deps import get_config, get_db
from stocks.db.models import DailyPrice, StrategySignal
from stocks.services.strategies.registry import get_strategy, list_strategies, strategy_meta

router = APIRouter(prefix="/strategies", tags=["Strategy Screener"])


# ── Schemas ───────────────────────────────────────────────────────────────────
class StrategyMetaResponse(BaseModel):
    id: str
    name: str
    version: str
    description: str
    param_schema: dict
    data_needs: dict


class StrategySignalRow(BaseModel):
    symbol_id: int
    symbol: str
    company_name: str
    strategy_id: str
    as_of: str
    signal: str
    score: float | None = None
    last_close: float | None = None
    entry_ref: float | None = None
    initial_stop: float | None = None
    target: float | None = None
    risk_pct: float | None = None
    rr: float | None = None
    key_metrics: dict = {}
    gates: dict = {}
    reasons: list = []


class StrategySignalsResponse(BaseModel):
    strategy_id: str
    as_of: str | None = None
    stale: bool = False
    counts: dict
    rows: list[StrategySignalRow]


def _parse(blob: str | None, fallback):
    if not blob:
        return fallback
    try:
        return json.loads(blob)
    except (ValueError, TypeError):
        return fallback


def _row_to_dict(s: StrategySignal) -> dict:
    return {
        "symbol_id": s.symbol_id,
        "symbol": s.symbol,
        "company_name": s.company_name,
        "strategy_id": s.strategy_id,
        "as_of": s.as_of.strftime("%Y-%m-%d") if s.as_of else "",
        "signal": s.signal,
        "score": s.score,
        "last_close": float(s.last_close) if s.last_close is not None else None,
        "entry_ref": float(s.entry_ref) if s.entry_ref is not None else None,
        "initial_stop": float(s.initial_stop) if s.initial_stop is not None else None,
        "target": float(s.target) if s.target is not None else None,
        "risk_pct": s.risk_pct,
        "rr": s.rr,
        "key_metrics": _parse(s.key_metrics, {}),
        "gates": _parse(s.gates, {}),
        "reasons": _parse(s.reasons, []),
    }


# ── Routes ────────────────────────────────────────────────────────────────────
@router.get("", response_model=list[StrategyMetaResponse])
def get_strategies():
    """Registry list for the strategy dropdown (id, name, version, param_schema)."""
    return [strategy_meta(s) for s in list_strategies()]


@router.get("/matrix")
def get_strategy_matrix(
    signals: str | None = None,        # CSV filter; a row is kept if ANY strategy matches
    min_score: float = 0.0,
    only_active: bool = True,          # drop rows where every strategy is NONE
    limit: int = 2500,
    db: Session = Depends(get_db),
):
    """Symbol × strategy grid: one row per symbol, a Buy/Watch/Sell/Near-miss cell per
    strategy, plus a consensus tally. Pivots the materialized signals in one query."""
    strategies = list_strategies()
    sids = [a.id for a in strategies]
    wanted = [s.strip().upper() for s in signals.split(",") if s.strip()] if signals else None

    rows = db.scalars(
        select(StrategySignal).where(StrategySignal.strategy_id.in_(sids))
    ).all()

    by_symbol: dict[str, dict] = {}
    for r in rows:
        cell = by_symbol.setdefault(r.symbol, {
            "symbol": r.symbol, "company_name": r.company_name,
            "cells": {}, "consensus": {"BUY": 0, "WATCH": 0, "SELL": 0}, "best_score": 0.0,
        })
        cell["cells"][r.strategy_id] = {"signal": r.signal, "score": r.score}
        if r.signal in cell["consensus"]:
            cell["consensus"][r.signal] += 1
        if r.score and r.score > cell["best_score"]:
            cell["best_score"] = r.score

    out = list(by_symbol.values())
    if only_active:
        out = [x for x in out if any(c["signal"] != "NONE" for c in x["cells"].values())]
    if wanted:
        out = [x for x in out if any(c["signal"] in wanted for c in x["cells"].values())]
    if min_score:
        out = [x for x in out if x["best_score"] >= min_score]
    out.sort(key=lambda x: (x["consensus"]["BUY"], x["consensus"]["WATCH"], x["best_score"]), reverse=True)
    out = out[:limit]

    as_of = db.scalar(select(func.max(StrategySignal.as_of)))
    latest_price_date = db.scalar(select(func.max(DailyPrice.trading_date)))
    return {
        "strategies": [{"id": a.id, "name": a.name} for a in strategies],
        "as_of": as_of.strftime("%Y-%m-%d") if as_of else None,
        "stale": bool(as_of and latest_price_date and as_of < latest_price_date),
        "rows": out,
    }


@router.get("/{strategy_id}/signals", response_model=StrategySignalsResponse)
def get_strategy_signals(
    strategy_id: str,
    signal: str | None = None,   # CSV e.g. "BUY,WATCH"; default BUY+WATCH
    min_score: float = 0.0,
    limit: int = 2500,
    db: Session = Depends(get_db),
):
    """Materialized signals for a strategy, default sort score desc (FR-5.1/5.2/5.5)."""
    if get_strategy(strategy_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown strategy '{strategy_id}'")

    wanted = (
        [s.strip().upper() for s in signal.split(",") if s.strip()]
        if signal else ["BUY", "WATCH"]
    )

    stmt = select(StrategySignal).where(StrategySignal.strategy_id == strategy_id)
    if wanted:
        stmt = stmt.where(StrategySignal.signal.in_(wanted))
    if min_score:
        stmt = stmt.where(StrategySignal.score >= min_score)
    # Plain DESC (no NULLS LAST): SQL Server rejects "NULLS LAST" syntax, and it sorts
    # NULLs last on DESC anyway; our NONE rows carry score 0.0 (not NULL) regardless.
    stmt = stmt.order_by(StrategySignal.score.desc()).limit(limit)
    rows = list(db.scalars(stmt).all())

    # Counts across ALL signals for this strategy (independent of the active filter).
    counts = {"scanned": 0, "BUY": 0, "WATCH": 0, "SELL": 0, "NONE": 0}
    for sig, cnt in db.execute(
        select(StrategySignal.signal, func.count())
        .where(StrategySignal.strategy_id == strategy_id)
        .group_by(StrategySignal.signal)
    ).all():
        counts[sig] = cnt
        counts["scanned"] += cnt

    as_of = db.scalar(
        select(func.max(StrategySignal.as_of)).where(StrategySignal.strategy_id == strategy_id)
    )
    latest_price_date = db.scalar(select(func.max(DailyPrice.trading_date)))
    stale = bool(as_of and latest_price_date and as_of < latest_price_date)

    return {
        "strategy_id": strategy_id,
        "as_of": as_of.strftime("%Y-%m-%d") if as_of else None,
        "stale": stale,
        "counts": counts,
        "rows": [_row_to_dict(r) for r in rows],
    }


@router.get("/{strategy_id}/signals/{symbol}", response_model=StrategySignalRow)
def get_strategy_signal_detail(strategy_id: str, symbol: str, db: Session = Depends(get_db)):
    """Full detail for one symbol: gates pass/fail, key metrics, reasons (FR-5.3)."""
    sym = symbol.strip().upper()
    if not sym.endswith(".NS") and not sym.startswith("^"):
        sym = f"{sym}.NS"
    row = db.scalar(
        select(StrategySignal).where(
            StrategySignal.strategy_id == strategy_id, StrategySignal.symbol == sym
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"No signal for {sym} / {strategy_id}")
    return _row_to_dict(row)


def _recompute_worker(request: Request, strategy_id: str, params: dict | None, force_market_ok: bool):
    from stocks.services.strategy_screener import StrategyScreenerService

    cfg = get_config(request)
    session = request.app.state.db_manager.get_session()
    try:
        StrategyScreenerService(cfg, session).refresh_all_signals(
            strategy_id, params=params, force_market_ok=force_market_ok
        )
    except Exception:
        pass
    finally:
        session.close()


@router.post("/{strategy_id}/recompute")
def recompute_strategy(
    strategy_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    body: dict | None = Body(default=None),
):
    """Rebuild the materialized signals in the background (manual run).

    Optional body:
      * ``params``          — overrides strategy defaults (clamped to min/max, AC-5.1).
      * ``force_market_ok`` — bypass the regime gate (§0.5) so BUYs can fire regardless
                              of the index/breadth state (testing / corrective tapes).
    """
    if get_strategy(strategy_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown strategy '{strategy_id}'")
    body = body if isinstance(body, dict) else {}
    params = body.get("params")
    force_market_ok = bool(body.get("force_market_ok", False))
    background_tasks.add_task(_recompute_worker, request, strategy_id, params, force_market_ok)
    return {"message": f"Recomputing '{strategy_id}' signals in the background."}
