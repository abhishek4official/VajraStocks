import subprocess
import sys
import time
from pathlib import Path

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import scoped_session, sessionmaker

from stocks.db.models import Base
from stocks.utils.exceptions import DatabaseConnectionError, DatabaseExecutionError


def _detect_provider(connection_string: str) -> str:
    """Detects the database provider from the connection string prefix."""
    cs = connection_string.lower()
    if cs.startswith("sqlite"):
        return "sqlite"
    if cs.startswith("postgresql") or cs.startswith("postgres"):
        return "postgresql"
    if cs.startswith("mssql"):
        return "mssql"
    return "unknown"


# ── MSSQL ODBC driver pre-check ──────────────────────────────────────────────

def _check_mssql_odbc_driver() -> None:
    """Validates that pyodbc and a Microsoft ODBC driver are installed before
    attempting any MSSQL connection, so users get a clear actionable message
    instead of a cryptic traceback.
    """
    try:
        import pyodbc  # noqa: F401
    except ImportError:
        raise DatabaseConnectionError(
            "The 'pyodbc' package is not installed. "
            "Install it with: pip install pyodbc"
        )

    try:
        import pyodbc as _pyodbc
        drivers = [d for d in _pyodbc.drivers() if "SQL Server" in d or "ODBC Driver" in d]
        if not drivers:
            raise DatabaseConnectionError(
                "No Microsoft ODBC Driver for SQL Server found on this system. "
                "Download and install it from: "
                "https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server"
            )
        logger.debug(f"MSSQL ODBC drivers found: {drivers}")
    except DatabaseConnectionError:
        raise
    except Exception as exc:
        logger.warning(f"Could not enumerate ODBC drivers: {exc}")


# ── MSSQL LocalDB helpers (Windows-only) ────────────────────────────────────

def _localdb_pipe() -> str:
    """Returns the named pipe for MSSQLLocalDB, or empty string if not ready."""
    try:
        r = subprocess.run(["sqllocaldb", "i", "MSSQLLocalDB"], capture_output=True, text=True, check=False)
        for line in r.stdout.splitlines():
            if "Instance pipe name" in line:
                pipe = line.split(":", 1)[-1].strip()
                return pipe
    except Exception:
        pass
    return ""


def _kill_stuck_sqlservr() -> None:
    """Kills any sqlservr.exe process that is holding a stale LocalDB handle."""
    try:
        r = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq sqlservr.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, check=False,
        )
        for line in r.stdout.strip().splitlines():
            parts = [p.strip('"') for p in line.split(",")]
            if len(parts) >= 2:
                pid = parts[1]
                subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True, check=False)
                logger.info(f"Killed stuck sqlservr.exe (PID {pid}).")
    except Exception as e:
        logger.debug(f"_kill_stuck_sqlservr: {e}")


def ensure_localdb_started() -> None:
    """Ensures the MSSQLLocalDB LocalDB instance is started and its named pipe is ready."""
    if sys.platform != "win32":
        return
    try:
        # Create instance if it doesn't exist yet
        check = subprocess.run(["sqllocaldb", "i", "MSSQLLocalDB"], capture_output=True, text=True, check=False)
        if check.returncode != 0:
            logger.warning("LocalDB 'MSSQLLocalDB' not found — creating...")
            subprocess.run(["sqllocaldb", "create", "MSSQLLocalDB"], capture_output=True, check=False)

        logger.info("Ensuring SQL Server LocalDB 'MSSQLLocalDB' instance is started...")

        # Only kill the orphaned process when the instance is confirmed Stopped AND no
        # named pipe is present. This prevents killing sqlservr.exe mid-sync when LocalDB
        # transiently reports "Stopped" while it is actually serving requests.
        is_stopped = "Stopped" in check.stdout
        if is_stopped and not _localdb_pipe():
            _kill_stuck_sqlservr()
            time.sleep(1)

        subprocess.run(["sqllocaldb", "start", "MSSQLLocalDB"], capture_output=True, check=False)

        # Wait up to 20 s for the named pipe to appear (process starts async)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            pipe = _localdb_pipe()
            if pipe:
                logger.info(f"SQL Server LocalDB 'MSSQLLocalDB' is ready (pipe: {pipe}).")
                return
            time.sleep(1)

        logger.warning("LocalDB started but named pipe not detected within 20 s — proceeding anyway.")
    except FileNotFoundError:
        logger.error("sqllocaldb not found. Install Microsoft SQL Server LocalDB.")
    except Exception as e:
        logger.error(f"Failed to start LocalDB: {e}")


def create_mssql_database_if_not_exists(connection_string: str) -> None:
    """Connects to the MSSQL master DB and creates the target database if missing.

    Retries up to 3 times with a 3-second back-off to handle the window between
    sqllocaldb reporting 'started' and the named pipe actually accepting connections.
    """
    base_url, query_params = connection_string.split("?") if "?" in connection_string else (connection_string, "")
    db_name = base_url.split("/")[-1]
    base_master_url = "/".join(base_url.split("/")[:-1]) + "/master"
    master_conn = f"{base_master_url}?{query_params}" if query_params else base_master_url

    logger.info(f"Checking if target database '{db_name}' exists on LocalDB...")
    last_exc: Exception | None = None
    for attempt in range(1, 4):
        master_engine = create_engine(master_conn, isolation_level="AUTOCOMMIT")
        try:
            with master_engine.connect() as conn:
                # Check if already attached
                already = conn.execute(text(f"SELECT DB_ID('{db_name}')")).scalar()
                if already is not None:
                    logger.info(f"Database '{db_name}' is already attached.")
                    return

                # Try to attach existing MDF first; fall back to CREATE for fresh installs.
                # LocalDB stores user DBs in %USERPROFILE% by default.
                import os as _os
                mdf = _os.path.join(_os.environ.get("USERPROFILE", "C:\\Users\\Default"), f"{db_name}.mdf")
                if _os.path.exists(mdf):
                    logger.info(f"Attaching existing MDF: {mdf}")
                    conn.execute(text(
                        f"CREATE DATABASE [{db_name}] ON (FILENAME = N'{mdf}') FOR ATTACH_REBUILD_LOG;"
                    ))
                else:
                    conn.execute(text(f"CREATE DATABASE [{db_name}];"))
                logger.info(f"Database '{db_name}' verified / created successfully.")
            master_engine.dispose()
            return
        except OperationalError as e:
            last_exc = e
            logger.warning(f"MSSQL master connection attempt {attempt}/3 failed — retrying in 3 s...")
            master_engine.dispose(close=True)
            time.sleep(3)
        except Exception as e:
            master_engine.dispose(close=True)
            raise DatabaseConnectionError(f"MSSQL bootstrap failed: {e}") from e

    logger.error(f"Failed to connect to MSSQL master after 3 attempts: {last_exc}")
    raise DatabaseConnectionError(f"MSSQL bootstrap failed: {last_exc}") from last_exc


# ── SQLite helpers ────────────────────────────────────────────────────────────

def ensure_sqlite_directory(connection_string: str) -> None:
    """Creates the parent directory for a SQLite database file if it does not exist."""
    # Strip the sqlite:/// prefix to get the file path
    path_str = connection_string.replace("sqlite:///", "").split("?")[0]
    if not path_str or path_str == ":memory:":
        return
    db_path = Path(path_str)
    if not db_path.is_absolute():
        db_path = Path.cwd() / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"SQLite database path: {db_path}")


# ── DatabaseManager ───────────────────────────────────────────────────────────

class DatabaseManager:
    """Manages SQLAlchemy engine, session pool, and DB bootstrap per provider."""

    def __init__(self, connection_string: str, pool_size: int = 5, max_overflow: int = 10, pool_recycle: int = 1800):
        self.connection_string = connection_string
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_recycle = pool_recycle
        self.provider = _detect_provider(connection_string)
        self.engine = None
        self.session_factory = None
        self.Session = None

    @classmethod
    def from_config(cls, config: "Config") -> "DatabaseManager":  # type: ignore[name-defined]
        """Construct from a Config object (legacy path — kept for CLI compatibility)."""
        return cls(
            connection_string=config.database.connection_string,
            pool_size=config.database.pool_size,
            max_overflow=config.database.max_overflow,
            pool_recycle=config.database.pool_recycle,
        )

    def initialize(self) -> None:
        """Bootstraps the database and initialises the SQLAlchemy engine + session pool."""
        # Provider-specific pre-flight
        if self.provider == "mssql":
            _check_mssql_odbc_driver()
            ensure_localdb_started()
            create_mssql_database_if_not_exists(self.connection_string)
        elif self.provider == "sqlite":
            ensure_sqlite_directory(self.connection_string)

        try:
            logger.info(f"Initialising SQLAlchemy engine [{self.provider}]...")
            if self.provider == "sqlite":
                self.engine = create_engine(
                    self.connection_string,
                    connect_args={"check_same_thread": False},
                    echo=False,
                )
            else:
                self.engine = create_engine(
                    self.connection_string,
                    pool_size=self.pool_size,
                    max_overflow=self.max_overflow,
                    pool_recycle=self.pool_recycle,
                    pool_pre_ping=True,
                    echo=False,
                )

            # Verify connectivity
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
            self.Session = scoped_session(self.session_factory)
            logger.info("Database connection pool initialised successfully.")

        except Exception as e:
            logger.critical(f"SQLAlchemy initialisation failed: {e}")
            raise DatabaseConnectionError(f"Failed to initialise database: {e}") from e

    def create_tables_directly(self) -> None:
        """Creates all tables from SQLAlchemy metadata (used for fresh SQLite installs)."""
        if self.engine is None:
            raise DatabaseConnectionError("DatabaseManager not initialised. Call initialize() first.")
        try:
            logger.info("Creating tables via SQLAlchemy metadata...")
            Base.metadata.create_all(self.engine)
            logger.info("All tables created/verified successfully.")
        except Exception as e:
            raise DatabaseExecutionError(f"Failed to create tables: {e}") from e

    def ensure_columns(self) -> None:
        """Adds columns missing from EXISTING tables (idempotent, dialect-aware).

        ``Base.metadata.create_all`` only creates missing *tables* — it never
        ALTERs an existing one. New columns added to a model (e.g. the MTF/risk
        fields on ``screening_snapshots``) must be patched in here so they work
        on the live MSSQL/Postgres database, not just fresh SQLite installs.
        """
        if self.engine is None:
            raise DatabaseConnectionError("DatabaseManager not initialised. Call initialize() first.")

        from sqlalchemy import inspect as sa_inspect

        dialect = self.engine.dialect.name  # 'mssql' / 'sqlite' / 'postgresql'
        # (table, column, generic_type, mssql_type)
        specs = [
            ("screening_snapshots", "atr_pct",              "FLOAT",        "FLOAT"),
            ("screening_snapshots", "vol_class",            "VARCHAR(10)",  "VARCHAR(10)"),
            ("screening_snapshots", "regime_bias",          "VARCHAR(20)",  "VARCHAR(20)"),
            ("screening_snapshots", "weekly_trend",         "VARCHAR(10)",  "VARCHAR(10)"),
            ("screening_snapshots", "mtf_confirmed",        "BOOLEAN",      "BIT"),
            ("screening_snapshots", "ret_1w",               "FLOAT",        "FLOAT"),
            ("screening_snapshots", "ret_2w",               "FLOAT",        "FLOAT"),
            ("screening_snapshots", "ret_3w",               "FLOAT",        "FLOAT"),
            ("screening_snapshots", "ret_4w",               "FLOAT",        "FLOAT"),
            # New indicator snapshot fields
            ("screening_snapshots", "adx_14",               "FLOAT",        "FLOAT"),
            ("screening_snapshots", "trend_strength_class", "VARCHAR(10)",  "VARCHAR(10)"),
            ("screening_snapshots", "obv_trend",            "VARCHAR(10)",  "VARCHAR(10)"),
            ("screening_snapshots", "supertrend_dir",       "VARCHAR(10)",  "VARCHAR(10)"),
            ("screening_snapshots", "stoch_state",          "VARCHAR(15)",  "VARCHAR(15)"),
            # Volume profile
            ("screening_snapshots", "avg_traded_value",     "FLOAT",        "FLOAT"),
            ("screening_snapshots", "volume_breakout_ratio","FLOAT",        "FLOAT"),
            # Composite score columns
            ("screening_snapshots", "composite_score",      "FLOAT",        "FLOAT"),
            ("screening_snapshots", "trend_score_val",      "FLOAT",        "FLOAT"),
            ("screening_snapshots", "volume_score_val",     "FLOAT",        "FLOAT"),
            ("screening_snapshots", "rs_score_val",         "FLOAT",        "FLOAT"),
            ("screening_snapshots", "momentum_score_val",   "FLOAT",        "FLOAT"),
            # StochRSI snapshot columns
            ("screening_snapshots", "cmf_20",                       "FLOAT",        "FLOAT"),
            ("screening_snapshots", "cmf_20_prev",                  "FLOAT",        "FLOAT"),
            ("screening_snapshots", "cmf_crossed_above_zero",       "BOOLEAN",      "BIT"),
            ("screening_snapshots", "cmf_score_val",                "FLOAT",        "FLOAT"),
            ("screening_snapshots", "breakout_score_val",           "FLOAT",        "FLOAT"),
            ("screening_snapshots", "stochrsi_k",                   "FLOAT",        "FLOAT"),
            ("screening_snapshots", "stochrsi_d",                   "FLOAT",        "FLOAT"),
            ("screening_snapshots", "stochrsi_zone",                "VARCHAR(15)",  "VARCHAR(15)"),
            ("screening_snapshots", "stochrsi_bullish_xover_days_ago", "INTEGER",   "INT"),
            ("screening_snapshots", "stochrsi_bearish_xover_days_ago", "INTEGER",   "INT"),
            # Crossover recency columns
            ("screening_snapshots", "days_since_price_sma20_bull", "INTEGER", "INT"),
            ("screening_snapshots", "days_since_price_sma50_bull", "INTEGER", "INT"),
            ("screening_snapshots", "days_since_price_ema20_bull", "INTEGER", "INT"),
            ("screening_snapshots", "days_since_ema9_ema20_bull",  "INTEGER", "INT"),
            ("screening_snapshots", "days_since_ema9_ema20_bear",  "INTEGER", "INT"),
            ("screening_snapshots", "days_since_sma20_sma50_bull", "INTEGER", "INT"),
            ("screening_snapshots", "days_since_macd_bull",        "INTEGER", "INT"),
            ("screening_snapshots", "days_since_macd_bear",        "INTEGER", "INT"),
            ("screening_snapshots", "days_since_cmf_bull",         "INTEGER", "INT"),
            ("screening_snapshots", "days_since_cmf_bear",         "INTEGER", "INT"),
            ("screening_snapshots", "ema9_ema20_spread",    "FLOAT",   "FLOAT"),
            ("screening_snapshots", "macd_histogram_slope", "FLOAT",   "FLOAT"),
            ("screening_snapshots", "macd_above_zero",      "BOOLEAN", "BIT"),
            ("screening_snapshots", "cmf_slope_5d",         "FLOAT",   "FLOAT"),
            # EOD import provenance column
            ("daily_prices",        "data_source",          "VARCHAR(20)",  "VARCHAR(20)"),
            # New DailyIndicator columns
            ("daily_indicators",    "ema_9",                "FLOAT",        "FLOAT"),
            ("daily_indicators",    "ema_20",               "FLOAT",        "FLOAT"),
            ("daily_indicators",    "adx_14",               "FLOAT",        "FLOAT"),
            ("daily_indicators",    "plus_di",              "FLOAT",        "FLOAT"),
            ("daily_indicators",    "minus_di",             "FLOAT",        "FLOAT"),
            ("daily_indicators",    "obv",                  "FLOAT",        "FLOAT"),
            ("daily_indicators",    "supertrend",           "FLOAT",        "FLOAT"),
            ("daily_indicators",    "supertrend_dir",       "VARCHAR(10)",  "VARCHAR(10)"),
            ("daily_indicators",    "stoch_k",              "FLOAT",        "FLOAT"),
            ("daily_indicators",    "stoch_d",              "FLOAT",        "FLOAT"),
            ("daily_indicators",    "cmf_20",               "FLOAT",        "FLOAT"),
            ("daily_indicators",    "stochrsi_k",           "FLOAT",        "FLOAT"),
            ("daily_indicators",    "stochrsi_d",           "FLOAT",        "FLOAT"),
            ("daily_indicators",    "stochrsi_bullish_xover", "BOOLEAN",    "BIT"),
            ("daily_indicators",    "stochrsi_bearish_xover", "BOOLEAN",    "BIT"),
        ]
        insp = sa_inspect(self.engine)
        existing_by_table: dict[str, set[str]] = {}
        for table, col, generic_type, mssql_type in specs:
            if table not in existing_by_table:
                try:
                    existing_by_table[table] = {c["name"] for c in insp.get_columns(table)}
                except Exception:
                    existing_by_table[table] = set()  # table absent — create_all will build it

            cols = existing_by_table[table]
            if not cols or col in cols:
                continue  # table not present yet, or column already exists

            col_type = mssql_type if dialect == "mssql" else generic_type
            add_kw = "ADD" if dialect == "mssql" else "ADD COLUMN"
            ddl = f"ALTER TABLE {table} {add_kw} {col} {col_type}"
            try:
                with self.engine.begin() as conn:
                    conn.execute(text(ddl))
                cols.add(col)
                logger.info(f"ensure_columns: added {table}.{col} ({col_type})")
            except Exception as e:
                logger.warning(f"ensure_columns: could not add {table}.{col}: {e}")

        # Widen regime_bias from VARCHAR(10) to VARCHAR(20) for 5-tier values (VERY_BULLISH = 12 chars)
        try:
            if dialect == "mssql":
                widen_ddl = "ALTER TABLE screening_snapshots ALTER COLUMN regime_bias VARCHAR(20) NULL"
            elif dialect == "postgresql":
                widen_ddl = "ALTER TABLE screening_snapshots ALTER COLUMN regime_bias TYPE VARCHAR(20)"
            else:
                widen_ddl = None  # SQLite doesn't enforce VARCHAR length
            if widen_ddl:
                with self.engine.begin() as conn:
                    conn.execute(text(widen_ddl))
                logger.info("ensure_columns: widened screening_snapshots.regime_bias to VARCHAR(20)")
        except Exception as e:
            logger.debug(f"ensure_columns: regime_bias widen skipped (may already be correct width): {e}")

    def get_session(self):
        """Returns a new isolated database session."""
        if self.session_factory is None:
            raise DatabaseConnectionError("DatabaseManager not initialised. Call initialize() first.")
        return self.session_factory()

    def remove_session(self) -> None:
        """Cleans up the scoped session."""
        if self.Session is not None:
            self.Session.remove()

    def dispose(self) -> None:
        """Disposes the engine connection pool, forcibly closing all connections.

        close=True ensures checked-out connections (e.g. from a background sync
        thread still in flight) are also closed, so MSSQL/LocalDB releases its
        process cleanly instead of hanging until timeout.
        """
        if self.engine is not None:
            logger.info("Disposing database engine pool...")
            self.engine.dispose(close=True)
