"""Persist and reload backtest results (V2.0 spec M2).

Stores a run's params, the computed metric set, and the per-trade audit trail so results
are durable, listable, and reproducible — the antithesis of the deleted fake backtester.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from stocks.db.models import BacktestMetric, BacktestRun, BacktestTrade
from stocks.services.quant.backtest.engine import BacktestResult

_METRIC_FIELDS = (
    "total_return",
    "cagr",
    "max_drawdown",
    "win_rate",
    "profit_factor",
    "sharpe_ratio",
)


class BacktestRepository:
    """Read/write access to stored backtest runs."""

    def __init__(self, session: Session):
        self.session = session

    def save(
        self,
        *,
        symbol: str,
        signal: str,
        result: BacktestResult,
        params: dict[str, Any] | None = None,
        start: dt.date | None = None,
        end: dt.date | None = None,
        store_equity_curve: bool = True,
    ) -> int:
        """Persist a backtest result; returns the new run id."""
        run = BacktestRun(
            symbol=symbol,
            signal=signal,
            params_json=json.dumps(params or {}),
            start_date=start,
            end_date=end,
            trades_count=len(result.trades),
            equity_curve_json=json.dumps(result.equity_curve) if store_equity_curve else None,
        )
        for field in _METRIC_FIELDS:
            run.metrics.append(BacktestMetric(metric=field, value=float(getattr(result.metrics, field))))
        for t in result.trades:
            run.trades.append(
                BacktestTrade(
                    entry_date=t.entry_date,
                    entry_price=t.entry_price,
                    exit_date=t.exit_date,
                    exit_price=t.exit_price,
                    qty=t.qty,
                    return_pct=t.return_pct,
                    reason=t.reason,
                )
            )
        self.session.add(run)
        self.session.commit()
        return run.id

    def get(self, backtest_id: int) -> BacktestRun | None:
        """Return a run (with metrics/trades relationships) by id, or None."""
        return self.session.get(BacktestRun, backtest_id)

    def get_metrics(self, backtest_id: int) -> dict[str, float]:
        """Return the stored metric set for a run as ``{metric: value}``."""
        rows = self.session.execute(
            select(BacktestMetric).where(BacktestMetric.backtest_id == backtest_id)
        ).scalars()
        return {r.metric: r.value for r in rows}

    def list(self, symbol: str | None = None) -> list[BacktestRun]:
        """List runs (optionally filtered by symbol), newest first."""
        stmt = select(BacktestRun)
        if symbol is not None:
            stmt = stmt.where(BacktestRun.symbol == symbol)
        stmt = stmt.order_by(BacktestRun.created_at.desc(), BacktestRun.id.desc())
        return list(self.session.execute(stmt).scalars())
