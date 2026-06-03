"""FastAPI dependencies — sessions and settings resolved from app.state (set by lifespan)."""

from collections.abc import Generator

from fastapi import Request
from sqlalchemy.orm import Session


def get_db(request: Request) -> Generator[Session, None, None]:
    """Yields a fresh database session, closed after the request completes."""
    db_manager = request.app.state.db_manager
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()


def get_settings(request: Request):
    """Returns the SettingsService bound to the request's db session."""
    from stocks.services.settings_service import SettingsService
    session = request.app.state.db_manager.get_session()
    return SettingsService(session)
