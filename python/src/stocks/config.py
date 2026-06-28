"""Application configuration.

Phase 1 strategy:
- Config.load() from config.yaml is kept for the CLI (sync, bootstrap_symbols, etc.)
- The FastAPI server uses SettingsService (DB-backed) via the lifespan
- DatabaseManager.from_config(config) keeps CLI compatibility
- Both paths converge: settings DB is seeded from config.yaml on first run
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    env: str = "production"
    name: str = "VajraStocks"


class DatabaseConfig(BaseModel):
    connection_string: str = "sqlite:///data/vajra.db"
    pool_size: int = 5
    max_overflow: int = 10
    pool_recycle: int = 1800


class StorageConfig(BaseModel):
    # Columnar analytical data plane (DuckDB + partitioned Parquet); see V2.0 spec §17/§18.
    columnar_data_dir: str = "data/columnar"


class DownloaderConfig(BaseModel):
    history_years: int = 3
    batch_size: int = 50
    rate_limit_per_second: int = 5
    max_retries: int = 5
    backoff_factor: float = 2.0
    timeout_seconds: int = 30


class SymbolsConfig(BaseModel):
    active_equities_url: str = "https://archives.nseindia.com/content/equities/EQUITY_L_ACTIVE.csv"
    fallback_csv_path: str = "config/EQUITY_L_ACTIVE.csv"
    default_indices: list[str] = Field(default_factory=lambda: ["^NSEI", "^NSEBANK"])
    include_indices: bool = True


class ValidationConfig(BaseModel):
    max_price_pct_change_limit: float = 0.50
    enable_volume_check: bool = True
    enable_empty_row_check: bool = True


class LoggingConfig(BaseModel):
    console_level: str = "INFO"
    file_level: str = "DEBUG"
    file_path: str = "logs/vajra.log"
    rotation: str = "10 MB"
    retention: str = "30 days"


class AIConfig(BaseModel):
    provider: str = "ollama"
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5-coder:7b"
    api_key: str = ""


class Config(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    downloader: DownloaderConfig = Field(default_factory=DownloaderConfig)
    symbols: SymbolsConfig = Field(default_factory=SymbolsConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    ai: AIConfig = Field(default_factory=AIConfig)

    @classmethod
    def load(cls, config_path: Path | None = None) -> "Config":
        """Load config from YAML file. Falls back to all defaults if file is missing."""
        if config_path is None:
            config_path = Path("config/config.yaml")

        if not config_path.exists():
            # Phase 1: no config.yaml required — use defaults (SQLite)
            return cls()

        with config_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        return cls(**data)
