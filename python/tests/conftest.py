import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool

from stocks.config import Config
from stocks.db.connection import DatabaseManager


@pytest.fixture(scope="session")
def test_config() -> Config:
    """Fixture that loads config and overrides DB to SQLite memory for safe testing."""
    config = Config.load()
    # Override database to in-memory SQLite for high-speed unit tests
    config.database.connection_string = "sqlite:///:memory:"
    config.symbols.fallback_csv_path = "tests/EQUITY_L_TEST.csv"
    return config


@pytest.fixture(scope="function")
def db_manager(test_config) -> DatabaseManager:
    """Fixture that initializes the DatabaseManager on the temporary SQLite database."""
    manager = DatabaseManager.from_config(test_config)
    # Redirect SQLAlchemy to temporary SQLite engine with StaticPool for safe multi-threaded sharing
    manager.engine = create_engine(
        test_config.database.connection_string, connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    manager.session_factory = sessionmaker(bind=manager.engine, expire_on_commit=False)
    manager.Session = scoped_session(manager.session_factory)

    # Direct DDL table creation bypasses migrations for speed
    manager.create_tables_directly()

    yield manager

    # Clean up
    manager.dispose()


@pytest.fixture(scope="function")
def db_session(db_manager):
    """Fixture that provides a scoped DB session that is rolled back after each test."""
    session = db_manager.get_session()
    yield session
    session.rollback()
    db_manager.remove_session()
