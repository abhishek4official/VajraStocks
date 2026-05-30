import os
from typing import List, Optional
from pydantic import BaseModel, Field
import yaml
from pathlib import Path

class AppConfig(BaseModel):
    env: str
    name: str

class DatabaseConfig(BaseModel):
    connection_string: str
    pool_size: int = 10
    max_overflow: int = 20
    pool_recycle: int = 1800

class DownloaderConfig(BaseModel):
    history_years: int = 3
    batch_size: int = 50
    rate_limit_per_second: int = 5
    max_retries: int = 5
    backoff_factor: float = 2.0
    timeout_seconds: int = 30

class SymbolsConfig(BaseModel):
    active_equities_url: str
    fallback_csv_path: str
    default_indices: List[str] = Field(default_factory=list)
    include_indices: bool = True

class ValidationConfig(BaseModel):
    max_price_pct_change_limit: float = 0.50
    enable_volume_check: bool = True
    enable_empty_row_check: bool = True

class LoggingConfig(BaseModel):
    console_level: str = "INFO"
    file_level: str = "DEBUG"
    file_path: str = "logs/nse_downloader.log"
    rotation: str = "10 MB"
    retention: str = "30 days"

class AIConfig(BaseModel):
    provider: str = "ollama"
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5-coder:7b"

class Config(BaseModel):
    app: AppConfig
    database: DatabaseConfig
    downloader: DownloaderConfig
    symbols: SymbolsConfig
    validation: ValidationConfig
    logging: LoggingConfig
    ai: AIConfig

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        if config_path is None:
            # Look in config/config.yaml relative to current working directory or absolute workspace path
            config_path = Path("config/config.yaml")
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found at {config_path}")
        
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            
        return cls(**data)
