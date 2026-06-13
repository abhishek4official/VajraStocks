"""
Top-N universe selection by average daily turnover (volume × close price).

Turnover-based ranking is preferred over raw volume because it correctly
weights large-cap stocks over low-priced high-volume penny stocks.
E.g. HDFCBANK at ₹923 × 27M shares/day >> IDEA at ₹14 × 523M shares/day.
"""

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

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
    query = text("""
        WITH ranked AS (
            SELECT
                s.id                AS symbol_id,
                s.symbol,
                s.company_name,
                AVG(
                    CAST(p.volume AS BIGINT) * CAST(p.[close] AS FLOAT)
                )                   AS avg_turnover,
                COUNT(p.trading_date) AS trading_days,
                ROW_NUMBER() OVER (
                    ORDER BY AVG(
                        CAST(p.volume AS BIGINT) * CAST(p.[close] AS FLOAT)
                    ) DESC
                )                   AS rn
            FROM daily_prices p
            JOIN symbols s ON s.id = p.symbol_id
            WHERE p.trading_date >= DATEADD(
                      DAY, -365,
                      (SELECT MAX(trading_date) FROM daily_prices)
                  )
              AND s.series    = 'EQ'
              AND s.is_active = 1
              AND p.granularity = '1d'
            GROUP BY s.id, s.symbol, s.company_name
            HAVING COUNT(p.trading_date) >= :min_days
        )
        SELECT
            symbol_id,
            symbol,
            company_name,
            CAST(avg_turnover AS BIGINT) AS avg_turnover,
            trading_days,
            rn AS rank
        FROM ranked
        WHERE rn <= :top_n
        ORDER BY rn
    """)

    df = pd.read_sql(query, engine, params={"min_days": min_days, "top_n": top_n})
    return df


def get_universe_symbol_ids(engine: Engine, top_n: int = UNIVERSE_TOP_N) -> list[int]:
    return get_universe(engine, top_n=top_n)["symbol_id"].tolist()
