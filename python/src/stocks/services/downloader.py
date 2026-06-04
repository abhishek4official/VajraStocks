import datetime
import time
from typing import Any

import pandas as pd
import yfinance as yf
from loguru import logger

from stocks.config import Config
from stocks.utils.exceptions import DownloaderError


def retry_on_failure(max_retries: int = 3, backoff_factor: float = 2.0):
    """Decorator to retry a function execution with exponential backoff on downloader failures."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            last_err = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_err = e
                    err_msg = str(e).lower()

                    # Detect potential rate limits (HTTP 429) or timeouts
                    is_rate_limit = "429" in err_msg or "too many requests" in err_msg

                    sleep_time = backoff_factor * (2 ** (attempt - 1))
                    if is_rate_limit:
                        sleep_time *= 2.0  # Double sleep penalty for rate throttling
                        logger.warning(
                            f"Yahoo Finance rate limit hit. Retrying attempt {attempt}/{max_retries} in {sleep_time}s..."
                        )
                    else:
                        logger.warning(
                            f"Yahoo Finance download encountered error: {e}. "
                            f"Retrying attempt {attempt}/{max_retries} in {sleep_time}s..."
                        )
                    time.sleep(sleep_time)
            logger.error(f"Yahoo Finance operation {func.__name__} failed after {max_retries} attempts.")
            raise DownloaderError(f"Failed executing Yahoo Finance client: {last_err}") from last_err

        return wrapper

    return decorator


class DownloaderService:
    """Service wrapping Yahoo Finance client to fetch historical daily price and corporate actions safely."""

    def __init__(self, config: Config):
        self.config = config
        self.rate_limit_interval = 1.0 / config.downloader.rate_limit_per_second
        self.last_request_time = 0.0

    def _apply_rate_limiting(self) -> None:
        """Throttles outgoing requests to protect Yahoo Finance client from rate bans."""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.rate_limit_interval:
            sleep_needed = self.rate_limit_interval - elapsed
            time.sleep(sleep_needed)
        self.last_request_time = time.time()

    @retry_on_failure(max_retries=3, backoff_factor=2.0)
    def fetch_batch_data(self, tickers: list[str], start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
        """Fetches bulk historical price and action data for a list of tickers from Yahoo Finance."""
        self._apply_rate_limiting()

        logger.info(f"Downloading historical data for {len(tickers)} symbols from {start_date} to {end_date}...")

        # Fetch EOD and actions in a single batch call. auto_adjust=False preserves both Close & Adj Close.
        df = yf.download(
            tickers=tickers,
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            group_by="ticker",
            auto_adjust=False,
            actions=True,
            threads=True,
            timeout=self.config.downloader.timeout_seconds,
        )
        return df

    def parse_downloaded_data(
        self, df: pd.DataFrame, tickers: list[str]
    ) -> dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]]]]:
        """Parses the MultiIndex DataFrame returned by yfinance into price and corporate action lists per ticker."""
        results = {}

        if df.empty:
            logger.warning("Yahoo Finance download returned an empty DataFrame.")
            return {t: ([], []) for t in tickers}

        # Check if the columns index is MultiIndexed (occurs when multiple tickers are returned)
        is_multi = isinstance(df.columns, pd.MultiIndex)

        for ticker in tickers:
            prices = []
            actions = []

            try:
                # Isolate target columns for this ticker
                if is_multi:
                    if ticker not in df.columns.levels[0]:
                        logger.debug(f"Ticker {ticker} not found in MultiIndex columns.")
                        results[ticker] = ([], [])
                        continue
                    ticker_df = df[ticker].dropna(subset=["Close", "Volume"])
                else:
                    # Single ticker case (yfinance simplifies column keys)
                    ticker_df = df.dropna(subset=["Close", "Volume"])

                for idx, row in ticker_df.iterrows():
                    # Parse timestamp
                    trading_date = idx.date() if isinstance(idx, pd.Timestamp) else idx

                    # 1. Price Record
                    price_rec = {
                        "trading_date": trading_date,
                        "open": float(row["Open"]),
                        "high": float(row["High"]),
                        "low": float(row["Low"]),
                        "close": float(row["Close"]),
                        "adj_close": float(row["Adj Close"]),
                        "volume": int(row["Volume"]),
                        "granularity": "1d",
                    }
                    prices.append(price_rec)

                    # 2. Corporate Actions
                    dividend = float(row.get("Dividends", 0.0))
                    split = float(row.get("Stock Splits", 0.0))

                    if dividend > 0.0:
                        actions.append({"action_date": trading_date, "action_type": "DIVIDEND", "value": dividend})
                    if split > 0.0:
                        actions.append({"action_date": trading_date, "action_type": "SPLIT", "value": split})

                results[ticker] = (prices, actions)

            except Exception as e:
                logger.error(f"Error parsing downloaded data for ticker {ticker}: {e}")
                results[ticker] = ([], [])

        return results
