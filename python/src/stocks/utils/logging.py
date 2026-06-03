import sys
from pathlib import Path

from loguru import logger

from stocks.config import Config


def setup_logging(config: Config) -> None:
    """Configures the Loguru logger for both console and file output based on config.

    Ensures that log directories are automatically bootstrapped and log rotation/retention
    policies are enforced.
    """
    # Remove the default Loguru logger handler to prevent double logging
    logger.remove()

    # Ensure log directories exist
    log_file_path = Path(config.logging.file_path)
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Console Output Handler (Formatted for scanning in CLI)
    logger.add(
        sys.stderr,
        level=config.logging.console_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        backtrace=True,
        diagnose=config.app.env == "development",
    )

    # 2. File Output Handler (Thread-safe rotating logger with ZIP compression)
    logger.add(
        str(log_file_path),
        level=config.logging.file_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation=config.logging.rotation,
        retention=config.logging.retention,
        compression="zip",
        enqueue=True,  # Multiprocessing and thread-safe queueing
        backtrace=True,
        diagnose=True,
    )

    logger.info(f"Logging initialized successfully. Log output targeting: {log_file_path.resolve()}")
