"""Database-backed settings service — replaces config.yaml for runtime configuration."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from stocks.db.models import AppSetting

# ── Default settings seed ─────────────────────────────────────────────────────
# Format: (category, key, value, value_type, description, is_secret)
DEFAULT_SETTINGS: list[tuple[str, str, str, str, str, bool]] = [
    # APPLICATION
    ("APPLICATION", "app_name",          "VajraStocks",          "string",  "Display name",                              False),
    ("APPLICATION", "app_env",           "production",           "string",  "production or development",                 False),
    ("APPLICATION", "log_level_console", "INFO",                 "string",  "Console log level",                         False),
    ("APPLICATION", "log_level_file",    "DEBUG",                "string",  "File log level",                            False),
    ("APPLICATION", "log_file_path",     "logs/vajra.log",       "string",  "Log file path",                             False),
    ("APPLICATION", "log_rotation",      "10 MB",                "string",  "Log rotation size",                         False),
    ("APPLICATION", "log_retention",     "30 days",              "string",  "Log retention period",                      False),

    # DATABASE
    ("DATABASE", "db_provider",          "sqlite",               "string",  "sqlite / postgresql / mssql",               False),
    ("DATABASE", "db_connection_string", "sqlite:///data/vajra.db", "string", "Full SQLAlchemy connection URL",          False),
    ("DATABASE", "db_pool_size",         "5",                    "integer", "Connection pool size",                      False),
    ("DATABASE", "db_max_overflow",      "10",                   "integer", "Max pool overflow connections",             False),
    ("DATABASE", "db_pool_recycle",      "1800",                 "integer", "Pool recycle interval (seconds)",           False),

    # DOWNLOADER
    ("DOWNLOADER", "history_years",           "3",    "integer", "Years of historical data to download",     False),
    ("DOWNLOADER", "batch_size",              "50",   "integer", "Symbol batch size per download request",   False),
    ("DOWNLOADER", "rate_limit_per_second",   "5",    "integer", "Max yfinance requests per second",         False),
    ("DOWNLOADER", "max_retries",             "5",    "integer", "Max retry attempts per symbol",            False),
    ("DOWNLOADER", "backoff_factor",          "2.0",  "float",   "Exponential backoff multiplier",           False),
    ("DOWNLOADER", "timeout_seconds",         "30",   "integer", "HTTP timeout per request",                  False),

    # MARKET
    ("MARKET", "default_exchange",        "NSE",           "string",  "Active exchange code",                     False),
    ("MARKET", "active_exchanges",        '["NSE"]',       "json",    "List of enabled exchange codes",           False),
    ("MARKET", "rs_benchmark_symbol",     "^NSEI",         "string",  "Relative strength benchmark ticker",       False),
    ("MARKET", "validation_max_pct_change", "0.50",        "float",   "Max daily price change before flagging",   False),
    ("MARKET", "validation_enable_volume_check", "true",   "boolean", "Enable volume validation checks",          False),
    ("MARKET", "nse_equities_url",        "https://archives.nseindia.com/content/equities/EQUITY_L_ACTIVE.csv",
                                                           "string",  "NSE active equities CSV URL",              False),
    ("MARKET", "nse_fallback_csv_path",   "config/EQUITY_L_ACTIVE.csv",
                                                           "string",  "Fallback NSE CSV path",                    False),

    # AI
    ("AI", "ai_provider",   "ollama",                    "string",  "LLM provider: ollama / openai",     False),
    ("AI", "ai_base_url",   "http://localhost:11434",    "string",  "AI provider base URL",              False),
    ("AI", "ai_model",      "qwen2.5-coder:7b",          "string",  "Model name to use",                 False),
    ("AI", "ai_api_key",    "",                          "string",  "API key for cloud providers",       True),
    ("AI", "ai_temperature","0.2",                       "float",   "Default LLM temperature",           False),
]


class SettingsService:
    """Reads and writes application settings from/to the app_settings table."""

    def __init__(self, db_session: Session):
        self.db = db_session
        self._cache: dict[tuple[str, str], str] = {}
        self._loaded = False

    # ── Bootstrap ─────────────────────────────────────────────────────────────

    def seed_defaults(self, overwrite: bool = False) -> int:
        """Inserts default settings rows. Returns the number of rows inserted."""
        inserted = 0
        for category, key, value, value_type, description, is_secret in DEFAULT_SETTINGS:
            existing = self.db.scalar(
                select(AppSetting).where(AppSetting.category == category, AppSetting.key == key)
            )
            if existing is None:
                row = AppSetting(
                    category=category,
                    key=key,
                    value=value,
                    value_type=value_type,
                    description=description,
                    is_secret=is_secret,
                )
                self.db.add(row)
                inserted += 1
            elif overwrite:
                existing.value = value
        self.db.commit()
        self._loaded = False  # bust cache
        logger.info(f"Settings seed complete — {inserted} new defaults inserted.")
        return inserted

    def import_from_config(self, config: "Config") -> None:  # type: ignore[name-defined]
        """One-time migration: imports non-default values from a Config object into the DB."""
        overrides: list[tuple[str, str, str]] = [
            ("DATABASE", "db_connection_string", config.database.connection_string),
            ("DATABASE", "db_pool_size",         str(config.database.pool_size)),
            ("DATABASE", "db_max_overflow",      str(config.database.max_overflow)),
            ("DATABASE", "db_pool_recycle",      str(config.database.pool_recycle)),
            ("DOWNLOADER", "history_years",          str(config.downloader.history_years)),
            ("DOWNLOADER", "batch_size",             str(config.downloader.batch_size)),
            ("DOWNLOADER", "rate_limit_per_second",  str(config.downloader.rate_limit_per_second)),
            ("DOWNLOADER", "max_retries",            str(config.downloader.max_retries)),
            ("DOWNLOADER", "backoff_factor",         str(config.downloader.backoff_factor)),
            ("DOWNLOADER", "timeout_seconds",        str(config.downloader.timeout_seconds)),
            ("AI", "ai_provider",  config.ai.provider),
            ("AI", "ai_base_url",  config.ai.base_url),
            ("AI", "ai_model",     config.ai.model),
            ("MARKET", "nse_equities_url",   config.symbols.active_equities_url),
            ("MARKET", "nse_fallback_csv_path", config.symbols.fallback_csv_path),
            ("APPLICATION", "app_name", config.app.name),
            ("APPLICATION", "app_env",  config.app.env),
        ]
        for category, key, value in overrides:
            row = self.db.scalar(
                select(AppSetting).where(AppSetting.category == category, AppSetting.key == key)
            )
            if row:
                row.value = value
        self.db.commit()
        self._loaded = False
        logger.info("Imported config.yaml values into app_settings.")

    # ── Read ──────────────────────────────────────────────────────────────────

    def _load_all(self) -> None:
        if self._loaded:
            return
        rows = self.db.scalars(select(AppSetting)).all()
        self._cache = {(r.category, r.key): r.value for r in rows}
        self._loaded = True

    def _raw(self, category: str, key: str, default: str = "") -> str:
        self._load_all()
        return self._cache.get((category, key), default)

    def get_str(self, category: str, key: str, default: str = "") -> str:
        return self._raw(category, key, default)

    def get_int(self, category: str, key: str, default: int = 0) -> int:
        try:
            return int(self._raw(category, key, str(default)))
        except (ValueError, TypeError):
            return default

    def get_float(self, category: str, key: str, default: float = 0.0) -> float:
        try:
            return float(self._raw(category, key, str(default)))
        except (ValueError, TypeError):
            return default

    def get_bool(self, category: str, key: str, default: bool = False) -> bool:
        raw = self._raw(category, key, str(default)).lower()
        return raw in ("true", "1", "yes")

    def get_json(self, category: str, key: str, default: Any = None) -> Any:
        try:
            return json.loads(self._raw(category, key, "null"))
        except (ValueError, TypeError):
            return default

    # ── Write ─────────────────────────────────────────────────────────────────

    def set(self, category: str, key: str, value: Any) -> None:
        """Updates a single setting value."""
        str_value = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        row = self.db.scalar(
            select(AppSetting).where(AppSetting.category == category, AppSetting.key == key)
        )
        if row:
            row.value = str_value
        else:
            # create it on-the-fly (unusual but safe)
            self.db.add(AppSetting(category=category, key=key, value=str_value, value_type="string"))
        self.db.commit()
        self._cache[(category, key)] = str_value

    # ── Bulk read (for API) ────────────────────────────────────────────────────

    def all_settings(self) -> list[dict]:
        """Returns all settings as a list of dicts (secrets have value masked)."""
        rows = self.db.scalars(select(AppSetting).order_by(AppSetting.category, AppSetting.key)).all()
        return [
            {
                "id": r.id,
                "category": r.category,
                "key": r.key,
                "value": "••••••••" if r.is_secret and r.value else r.value,
                "value_type": r.value_type,
                "description": r.description,
                "is_secret": r.is_secret,
            }
            for r in rows
        ]

    def settings_by_category(self) -> dict[str, list[dict]]:
        """Returns settings grouped by category."""
        flat = self.all_settings()
        result: dict[str, list[dict]] = {}
        for item in flat:
            result.setdefault(item["category"], []).append(item)
        return result
