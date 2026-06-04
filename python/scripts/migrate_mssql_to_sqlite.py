"""One-time migration: copy all data from MSSQL LocalDB to a local SQLite file.

Usage:
    uv run python scripts/migrate_mssql_to_sqlite.py
"""

import sys
from pathlib import Path

from loguru import logger
from sqlalchemy import create_engine, insert, select

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from stocks.db.models import Base  # noqa: E402

MSSQL_URL = (
    "mssql+pyodbc://(localdb)\\MSSQLLocalDB/NSEStockData"
    "?driver=ODBC+Driver+17+for+SQL+Server&Trusted_Connection=yes&MultipleActiveResultSets=True"
)
SQLITE_PATH = Path(__file__).resolve().parent.parent / "data" / "vajra.db"
SQLITE_URL = f"sqlite:///{SQLITE_PATH.as_posix()}"


def main() -> None:
    logger.info(f"Source (MSSQL):      {MSSQL_URL.split('?')[0]}")
    logger.info(f"Destination (SQLite): {SQLITE_PATH}")

    # Prepare SQLite destination
    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if SQLITE_PATH.exists():
        backup = SQLITE_PATH.with_suffix(".db.bak")
        logger.warning(f"Existing SQLite DB found — backing up to {backup.name}")
        SQLITE_PATH.replace(backup)

    src_engine = create_engine(MSSQL_URL)
    dst_engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})

    # Create all tables in SQLite
    logger.info("Creating schema in SQLite...")
    Base.metadata.create_all(dst_engine)

    total_rows = 0
    # sorted_tables = FK dependency order (parents before children)
    with src_engine.connect() as src_conn, dst_engine.begin() as dst_conn:
        for table in Base.metadata.sorted_tables:
            rows = list(src_conn.execute(select(table)).mappings())
            if not rows:
                logger.info(f"  {table.name:<22} 0 rows")
                continue
            # Bulk insert in chunks to avoid SQLite's 999-variable limit
            data = [dict(r) for r in rows]
            chunk_size = max(1, 900 // max(1, len(table.columns)))
            for i in range(0, len(data), chunk_size):
                dst_conn.execute(insert(table), data[i : i + chunk_size])
            total_rows += len(data)
            logger.info(f"  {table.name:<22} {len(data)} rows")

    src_engine.dispose()
    dst_engine.dispose()

    logger.success(f"Migration complete — {total_rows} rows copied to {SQLITE_PATH}")
    logger.info("Next: update config.yaml connection_string to the SQLite URL.")


if __name__ == "__main__":
    main()
