"""Backfill the columnar BarStore from the transactional SQLite store.

One-time / incremental ETL that copies ``DailyPrice`` rows into Parquet partitions, plus
a small adapter that loads ``CorporateAction`` rows in the dict shape ``read_bars`` wants
for query-time adjustment. SQLite stays the system of record for actions and user state;
the BarStore is the analytical mirror of the price series.

See Doc/VajraStocks_V2.0_PRD_BRD_Architecture.md §18, §27.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from stocks.data.bar_store import BarStore
from stocks.db.models import CorporateAction, DailyPrice, Symbol

if TYPE_CHECKING:
    from stocks.config import Config


def load_actions(session: Session, symbol_id: int) -> list[dict[str, Any]]:
    """Return a symbol's corporate actions as ``[{action_date, action_type, value}]``."""
    rows = session.execute(
        select(
            CorporateAction.action_date,
            CorporateAction.action_type,
            CorporateAction.value,
        ).where(CorporateAction.symbol_id == symbol_id)
    ).all()
    return [
        {"action_date": r.action_date, "action_type": r.action_type, "value": float(r.value)}
        for r in rows
    ]


def _rows_to_df(rows: list[DailyPrice]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "trading_date": r.trading_date,
                "open": float(r.open),
                "high": float(r.high),
                "low": float(r.low),
                "close": float(r.close),
                "adj_close": float(r.adj_close),
                "volume": int(r.volume),
            }
            for r in rows
        ]
    )


def backfill_symbol(
    session: Session,
    store: BarStore,
    symbol_id: int,
    symbol: str,
    granularity: str = "1d",
    incremental: bool = False,
) -> int:
    """Copy one symbol's price series into the BarStore. Returns rows written.

    When ``incremental`` is set, only bars newer than the store's last mirrored date are
    fetched and written, so an already-mirrored symbol with no new bars writes nothing.
    """
    stmt = select(DailyPrice).where(
        DailyPrice.symbol_id == symbol_id, DailyPrice.granularity == granularity
    )
    if incremental:
        last = store.last_date(symbol, granularity)
        if last is not None:
            stmt = stmt.where(DailyPrice.trading_date > last)

    rows = session.execute(stmt.order_by(DailyPrice.trading_date)).scalars().all()
    if not rows:
        return 0

    return store.write_bars(symbol, _rows_to_df(rows), granularity=granularity)


def backfill_all(
    session: Session,
    store: BarStore,
    granularity: str = "1d",
    incremental: bool = False,
) -> dict[str, int]:
    """Backfill every symbol that has price data. Returns ``{symbol: rows_written}``."""
    symbols = session.execute(select(Symbol.id, Symbol.symbol)).all()
    written: dict[str, int] = {}
    for symbol_id, symbol in symbols:
        n = backfill_symbol(
            session, store, symbol_id, symbol, granularity=granularity, incremental=incremental
        )
        if n:
            written[symbol] = n
    return written


def sync_columnar_store(
    db_manager,
    config: Config,
    granularity: str = "1d",
    incremental: bool = True,
) -> dict[str, int]:
    """Post-sync job: mirror the SQLite price series into the columnar BarStore.

    Opens its own session, builds the store from config, and (by default) runs an
    incremental backfill so only symbols with new bars are rewritten. Intended to be
    invoked from the scheduler after an EOD sync completes. Returns ``{symbol: rows_written}``.
    """
    store = BarStore.from_config(config)
    session = db_manager.get_session()
    try:
        result = backfill_all(session, store, granularity=granularity, incremental=incremental)
        logger.info(f"Columnar backfill complete: {len(result)} symbols mirrored to BarStore.")
        return result
    finally:
        session.close()
