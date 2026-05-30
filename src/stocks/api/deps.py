from typing import Generator
from sqlalchemy.orm import Session
from stocks.config import Config
from stocks.db.connection import DatabaseManager

# Load application configuration statically
config = Config.load()

# Initialize dynamic LocalDB manager
db_manager = DatabaseManager(config)
db_manager.initialize()

def get_db() -> Generator[Session, None, None]:
    """Dependency that yields a fresh isolated database session and closes it after the request completes."""
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()
