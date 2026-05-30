import subprocess
import sys

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import scoped_session, sessionmaker

from stocks.config import Config
from stocks.db.models import Base
from stocks.utils.exceptions import DatabaseConnectionError, DatabaseExecutionError


def ensure_localdb_started() -> None:
    """Ensures SQL Server LocalDB instance is started under Windows."""
    if sys.platform != "win32":
        # LocalDB is Windows specific
        return

    try:
        # Check if sqllocaldb CLI is available
        result = subprocess.run(["sqllocaldb", "info", "MSSQLLocalDB"], capture_output=True, text=True, check=False)
        if result.returncode != 0:
            logger.warning("LocalDB instance 'MSSQLLocalDB' info check failed. Attempting to create it...")
            subprocess.run(["sqllocaldb", "create", "MSSQLLocalDB"], capture_output=True)

        # Try to start it
        logger.info("Ensuring SQL Server LocalDB 'MSSQLLocalDB' instance is started...")
        start_result = subprocess.run(
            ["sqllocaldb", "start", "MSSQLLocalDB"], capture_output=True, text=True, check=False
        )
        if start_result.returncode == 0:
            logger.info("SQL Server LocalDB 'MSSQLLocalDB' instance is active and running.")
        else:
            logger.warning(f"Starting 'MSSQLLocalDB' returned: {start_result.stderr.strip()}")
    except FileNotFoundError:
        logger.error("sqllocaldb executable not found. Please ensure Microsoft SQL Server LocalDB is installed.")
    except Exception as e:
        logger.error(f"Failed to check/start SQL Server LocalDB instance: {e}")


def create_database_if_not_exists(connection_string: str) -> None:
    """Connects to master DB and creates the target database if it does not exist."""
    try:
        # Extract database name and base connection parameters
        base_url, query_params = connection_string.split("?") if "?" in connection_string else (connection_string, "")
        db_name = base_url.split("/")[-1]

        # Build master connection string by swapping the target DB with 'master'
        base_master_url = "/".join(base_url.split("/")[:-1]) + "/master"
        master_connection_string = f"{base_master_url}?{query_params}" if query_params else base_master_url

        logger.info(f"Checking if target database '{db_name}' exists on LocalDB...")
        master_engine = create_engine(master_connection_string, isolation_level="AUTOCOMMIT")

        with master_engine.connect() as conn:
            # Check and create database if missing
            sql = text(f"IF DB_ID('{db_name}') IS NULL CREATE DATABASE [{db_name}];")
            conn.execute(sql)
            logger.info(f"Database '{db_name}' verified / created successfully.")

        master_engine.dispose()
    except OperationalError as e:
        logger.error(f"Failed to connect to master database: {e}")
        err_msg = str(e).lower()
        if "driver" in err_msg or "odbc" in err_msg:
            logger.critical(
                "Microsoft ODBC Driver for SQL Server is missing or misconfigured in config.yaml! "
                "Please verify that 'ODBC Driver 17 for SQL Server' or similar is installed."
            )
        raise DatabaseConnectionError(f"Database bootstrap failed: {e}") from e
    except Exception as e:
        raise DatabaseConnectionError(f"Database bootstrap failed: {e}") from e


class DatabaseManager:
    """Manages SQLAlchemy engine sessions, connection pool, and migrations bootstrapping."""

    def __init__(self, config: Config):
        self.config = config
        self.connection_string = config.database.connection_string
        self.engine = None
        self.session_factory = None
        self.Session = None

    def initialize(self) -> None:
        """Bootstraps LocalDB, creates DB if missing, and initializes SQLAlchemy engine & sessions."""
        ensure_localdb_started()
        create_database_if_not_exists(self.connection_string)

        try:
            logger.info("Initializing SQLAlchemy Engine and Connection Pool...")
            self.engine = create_engine(
                self.connection_string,
                pool_size=self.config.database.pool_size,
                max_overflow=self.config.database.max_overflow,
                pool_recycle=self.config.database.pool_recycle,
                echo=False,
            )

            # Verify the connection works
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
            self.Session = scoped_session(self.session_factory)
            logger.info("Database connection pool initialized successfully.")

        except Exception as e:
            logger.critical(f"SQLAlchemy initialization failed: {e}")
            raise DatabaseConnectionError(f"Failed to initialize database session pool: {e}") from e

    def create_tables_directly(self) -> None:
        """Directly creates all tables using Base.metadata (useful for testing or fallback)."""
        if self.engine is None:
            raise DatabaseConnectionError("DatabaseManager not initialized. Call initialize() first.")
        try:
            logger.info("Creating tables via SQLAlchemy Metadata...")
            Base.metadata.create_all(self.engine)
            logger.info("Tables verified/created successfully.")
        except Exception as e:
            raise DatabaseExecutionError(f"Failed to create tables directly: {e}") from e

    def get_session(self):
        """Returns a new isolated database session."""
        if self.session_factory is None:
            raise DatabaseConnectionError("DatabaseManager not initialized. Call initialize() first.")
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
