import subprocess
import sys
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


# ── MSSQL LocalDB helpers (Windows-only) ────────────────────────────────────

def ensure_localdb_started() -> None:
    """Ensures SQL Server LocalDB instance is started (Windows only)."""
    if sys.platform != "win32":
        return
    try:
        result = subprocess.run(["sqllocaldb", "info", "MSSQLLocalDB"], capture_output=True, text=True, check=False)
        if result.returncode != 0:
            logger.warning("LocalDB 'MSSQLLocalDB' not found — attempting to create it...")
            subprocess.run(["sqllocaldb", "create", "MSSQLLocalDB"], capture_output=True)

        logger.info("Ensuring SQL Server LocalDB 'MSSQLLocalDB' instance is started...")
        start_result = subprocess.run(["sqllocaldb", "start", "MSSQLLocalDB"], capture_output=True, text=True, check=False)
        if start_result.returncode == 0:
            logger.info("SQL Server LocalDB 'MSSQLLocalDB' instance is active and running.")
        else:
            logger.warning(f"Starting 'MSSQLLocalDB' returned: {start_result.stderr.strip()}")
    except FileNotFoundError:
        logger.error("sqllocaldb executable not found. Please install Microsoft SQL Server LocalDB.")
    except Exception as e:
        logger.error(f"Failed to check/start LocalDB: {e}")


def create_mssql_database_if_not_exists(connection_string: str) -> None:
    """Connects to the MSSQL master DB and creates the target database if missing."""
    try:
        base_url, query_params = connection_string.split("?") if "?" in connection_string else (connection_string, "")
        db_name = base_url.split("/")[-1]
        base_master_url = "/".join(base_url.split("/")[:-1]) + "/master"
        master_conn = f"{base_master_url}?{query_params}" if query_params else base_master_url

        logger.info(f"Checking if target database '{db_name}' exists on LocalDB...")
        master_engine = create_engine(master_conn, isolation_level="AUTOCOMMIT")
        with master_engine.connect() as conn:
            conn.execute(text(f"IF DB_ID('{db_name}') IS NULL CREATE DATABASE [{db_name}];"))
            logger.info(f"Database '{db_name}' verified / created successfully.")
        master_engine.dispose()
    except OperationalError as e:
        logger.error(f"Failed to connect to MSSQL master: {e}")
        raise DatabaseConnectionError(f"MSSQL bootstrap failed: {e}") from e
    except Exception as e:
        raise DatabaseConnectionError(f"MSSQL bootstrap failed: {e}") from e


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
            ("screening_snapshots", "atr_pct",       "FLOAT",        "FLOAT"),
            ("screening_snapshots", "vol_class",     "VARCHAR(10)",  "VARCHAR(10)"),
            ("screening_snapshots", "regime_bias",   "VARCHAR(10)",  "VARCHAR(10)"),
            ("screening_snapshots", "weekly_trend",  "VARCHAR(10)",  "VARCHAR(10)"),
            ("screening_snapshots", "mtf_confirmed", "BOOLEAN",      "BIT"),
            ("screening_snapshots", "ret_1w",        "FLOAT",        "FLOAT"),
            ("screening_snapshots", "ret_2w",        "FLOAT",        "FLOAT"),
            ("screening_snapshots", "ret_3w",        "FLOAT",        "FLOAT"),
            ("screening_snapshots", "ret_4w",        "FLOAT",        "FLOAT"),
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
        """Disposes the engine connection pool."""
        if self.engine is not None:
            logger.info("Disposing database engine pool...")
            self.engine.dispose()
