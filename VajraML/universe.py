"""
Top-N universe selection by average daily turnover (volume × close price).

Turnover-based ranking is preferred over raw volume because it correctly
weights large-cap stocks over low-priced high-volume penny stocks.
E.g. HDFCBANK at ₹923 × 27M shares/day >> IDEA at ₹14 × 523M shares/day.
"""

from datetime import timedelta

import pandas as pd
from sqlalchemy import Float, cast, func, select
from sqlalchemy.engine import Engine

from stocks.db.models import DailyPrice, Symbol

from VajraML.config import UNIVERSE_MIN_DAYS, UNIVERSE_TOP_N


def get_universe(
    engine: Engine,
    top_n: int = UNIVERSE_TOP_N,
    min_days: int = UNIVERSE_MIN_DAYS,
) -> pd.DataFrame:
    """
    Return the top-N NSE EQ stocks by average daily turnover over the
    last 365 calendar days.  Only stocks with >= min_days trading days
    in that window qualify.

    Columns returned: symbol_id, symbol, company_name, avg_turnover,
    trading_days, rank.
    """
    # Resolve cutoff date from DB so it matches the actual data range
    with engine.connect() as conn:
        max_date = conn.execute(select(func.max(DailyPrice.trading_date))).scalar()
    cutoff = max_date - timedelta(days=365)

    avg_turnover = func.avg(
        cast(DailyPrice.volume, Float) * cast(DailyPrice.close, Float)
    ).label("avg_turnover")
    trading_days = func.count(DailyPrice.trading_date).label("trading_days")

    stmt = (
        select(
            Symbol.id.label("symbol_id"),
            Symbol.symbol,
            Symbol.company_name,
            avg_turnover,
            trading_days,
        )
        .join(Symbol, Symbol.id == DailyPrice.symbol_id)
        .where(
            DailyPrice.trading_date >= cutoff,
            Symbol.series == "EQ",
            Symbol.is_active == True,  # noqa: E712
            DailyPrice.granularity == "1d",
        )
        .group_by(Symbol.id, Symbol.symbol, Symbol.company_name)
        .having(func.count(DailyPrice.trading_date) >= min_days)
    )

    df = pd.read_sql(stmt, engine)
    df = df.sort_values("avg_turnover", ascending=False).head(top_n).reset_index(drop=True)
    df["rank"] = range(1, len(df) + 1)
    return df


def get_universe_symbol_ids(engine: Engine, top_n: int = UNIVERSE_TOP_N) -> list[int]:
    return get_universe(engine, top_n=top_n)["symbol_id"].tolist()
