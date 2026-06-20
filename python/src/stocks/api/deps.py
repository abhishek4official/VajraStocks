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


def get_settings(request: Request) -> Generator:
    """Yields a SettingsService bound to a fresh DB session, closed after the request."""
    from stocks.services.settings_service import SettingsService
    session = request.app.state.db_manager.get_session()
    try:
        yield SettingsService(session)
    finally:
        session.close()


def get_config(request: Request):
    """
    Builds a Config object entirely from DB-backed settings — no config.yaml involved.
    Used by sync and agent endpoints so they always reflect live DB values.
    """
    from stocks.config import (
        AIConfig, AppConfig, Config, DatabaseConfig,
        DownloaderConfig, SymbolsConfig, ValidationConfig,
    )
    from stocks.services.settings_service import SettingsService

    session = request.app.state.db_manager.get_session()
    try:
        s = SettingsService(session)
        return Config(
            app=AppConfig(
                name=s.get_str("APPLICATION", "app_name", "VajraStocks"),
                env=s.get_str("APPLICATION", "app_env", "production"),
            ),
            database=DatabaseConfig(
                connection_string=s.get_str("DATABASE", "db_connection_string", "sqlite:///data/vajra.db"),
                pool_size=s.get_int("DATABASE", "db_pool_size", 5),
                max_overflow=s.get_int("DATABASE", "db_max_overflow", 10),
                pool_recycle=s.get_int("DATABASE", "db_pool_recycle", 1800),
            ),
            downloader=DownloaderConfig(
                history_years=s.get_int("DOWNLOADER", "history_years", 3),
                batch_size=s.get_int("DOWNLOADER", "batch_size", 50),
                rate_limit_per_second=s.get_int("DOWNLOADER", "rate_limit_per_second", 5),
                max_retries=s.get_int("DOWNLOADER", "max_retries", 5),
                backoff_factor=s.get_float("DOWNLOADER", "backoff_factor", 2.0),
                timeout_seconds=s.get_int("DOWNLOADER", "timeout_seconds", 30),
            ),
            symbols=SymbolsConfig(
                active_equities_url=s.get_str(
                    "MARKET", "nse_equities_url",
                    "https://archives.nseindia.com/content/equities/EQUITY_L_ACTIVE.csv",
                ),
                fallback_csv_path=s.get_str("MARKET", "nse_fallback_csv_path", "config/EQUITY_L_ACTIVE.csv"),
            ),
            validation=ValidationConfig(
                max_price_pct_change_limit=s.get_float("MARKET", "validation_max_pct_change", 0.50),
                enable_volume_check=s.get_bool("MARKET", "validation_enable_volume_check", True),
            ),
            ai=AIConfig(
                provider=s.get_str("AI", "ai_provider", "ollama"),
                base_url=s.get_str("AI", "ai_base_url", "http://localhost:11434"),
                model=s.get_str("AI", "ai_model", "qwen2.5-coder:7b"),
                api_key=s.get_str("AI", "ai_api_key", ""),
            ),
        )
    finally:
        session.close()
