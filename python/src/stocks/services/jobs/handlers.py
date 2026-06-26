"""Built-in job handlers (V2.0 spec M1).

Registers long-running work as queue jobs so it runs off the request thread with progress
and cancel. Import this module once at startup to register the handlers.
"""

from __future__ import annotations

from sqlalchemy import select

from stocks.data.bar_store import BarStore
from stocks.data.backfill import backfill_symbol
from stocks.db.models import Symbol
from stocks.services.jobs.runner import JobCancelled, register_handler


@register_handler("columnar_backfill")
def columnar_backfill(job, session, set_progress, is_cancelled):
    """Mirror SQLite/MSSQL price history into the columnar BarStore, with progress + cancel.

    Replaces the synchronous /backtest/backfill (which blocked for minutes on ~2400 symbols).
    Params: ``{"incremental": bool, "columnar_data_dir": str}``.
    """
    import json

    params = json.loads(job.params_json or "{}")
    incremental = params.get("incremental", True)
    data_dir = params.get("columnar_data_dir", "data/columnar")
    store = BarStore(data_dir)

    symbols = session.execute(select(Symbol.id, Symbol.symbol)).all()
    total = len(symbols)
    written = 0
    for i, (symbol_id, symbol) in enumerate(symbols, start=1):
        if is_cancelled():
            raise JobCancelled()
        n = backfill_symbol(session, store, symbol_id, symbol, incremental=incremental)
        if n:
            written += n
        if i % 25 == 0 or i == total:
            set_progress(i, total)
    return {"symbols": total, "rows": written}
