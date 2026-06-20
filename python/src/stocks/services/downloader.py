import datetime
import time
from typing import Any

import pandas as pd
import yfinance as yf
from loguru import logger

from stocks.config import Config
from stocks.utils.exceptions import DownloaderError


import requests


def retry_on_failure(max_retries: int | None = None, backoff_factor: float | None = None):
    """Decorator to retry a function execution with exponential backoff on downloader failures."""

    def decorator(func):
        def wrapper(self, *args, **kwargs):
            # Resolve parameters from config if not explicitly overridden
            retries = max_retries if max_retries is not None else self.config.downloader.max_retries
            backoff = backoff_factor if backoff_factor is not None else self.config.downloader.backoff_factor

            last_err = None
            for attempt in range(1, retries + 1):
                try:
                    return func(self, *args, **kwargs)
                except Exception as e:
                    last_err = e
                    err_msg = str(e).lower()

                    # Detect potential rate limits (HTTP 429) or timeouts
                    is_rate_limit = "429" in err_msg or "too many requests" in err_msg or "rate limit" in err_msg

                    sleep_time = backoff * (2 ** (attempt - 1))
                    if is_rate_limit:
                        sleep_time *= 2.0  # Double sleep penalty for rate throttling
                        logger.warning(
                            f"Yahoo Finance rate limit hit. Retrying attempt {attempt}/{retries} in {sleep_time}s..."
                        )
                    else:
                        logger.warning(
                            f"Yahoo Finance download encountered error: {e}. "
                            f"Retrying attempt {attempt}/{retries} in {sleep_time}s..."
                        )
                    time.sleep(sleep_time)
            logger.error(f"Yahoo Finance operation {func.__name__} failed after {retries} attempts.")
            raise DownloaderError(f"Failed executing Yahoo Finance client: {last_err}") from last_err

        return wrapper

    return decorator


class DownloaderService:
    """Service wrapping Yahoo Finance client to fetch historical daily price and corporate actions safely."""

    def __init__(self, config: Config):
        self.config = config
        self.rate_limit_interval = 1.0 / config.downloader.rate_limit_per_second
        self.last_request_time = 0.0
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Creates a requests.Session with browser-like headers and retry adapters."""
        from requests.adapters import HTTPAdapter
        from urllib3.util import Retry

        session = requests.Session()

        # Mimic browser to prevent Yahoo Finance scraping blocks
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        })

        # Set up adapter level retries for connection pool limits or transient errors
        retries = Retry(
            total=self.config.downloader.max_retries,
            backoff_factor=self.config.downloader.backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=True,
        )

        adapter = HTTPAdapter(max_retries=retries)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        return session

    def _apply_rate_limiting(self) -> None:
        """Throttles outgoing requests to protect Yahoo Finance client from rate bans."""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.rate_limit_interval:
            sleep_needed = self.rate_limit_interval - elapsed
            time.sleep(sleep_needed)
        self.last_request_time = time.time()

    @retry_on_failure()
    def _fetch_single_ticker(self, ticker: str, start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
        """Fetches historical price and corporate action data for a single ticker."""
        self._apply_rate_limiting()

        exclusive_end_date = end_date + datetime.timedelta(days=1)

        # Call yf.download for a single ticker
        df = yf.download(
            tickers=ticker,
            start=start_date.strftime("%Y-%m-%d"),
            end=exclusive_end_date.strftime("%Y-%m-%d"),
            group_by="ticker",
            auto_adjust=False,
            actions=True,
            threads=False,  # Single ticker download, no threads needed
            timeout=self.config.downloader.timeout_seconds,
            session=self.session,
            progress=False,
        )

        if df is not None and not df.empty:
            # Flatten MultiIndex to single index for individual tickers
            if isinstance(df.columns, pd.MultiIndex):
                if ticker in df.columns.levels[0]:
                    df = df[ticker]
                elif hasattr(df.columns, "levels") and len(df.columns.levels) > 1 and ticker in df.columns.levels[1]:
                    df = df.xs(ticker, axis=1, level=1)

        if df is None or df.empty:
            raise DownloaderError(f"Yahoo Finance returned empty data for {ticker}")

        return df

    def fetch_batch_data(self, tickers: list[str], start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
        """Fetches historical price and action data for a list of tickers from Yahoo Finance."""
        logger.info(f"Downloading historical data for {len(tickers)} symbols from {start_date} to {end_date}...")

        dfs = []

        for idx, ticker in enumerate(tickers, 1):
            logger.info(f"[{idx}/{len(tickers)}] Downloading {ticker}...")
            try:
                # Retrieve single ticker data with retry decorator protection
                df = self._fetch_single_ticker(ticker, start_date, end_date)
                
                # Convert columns to MultiIndex if we are downloading a batch of tickers
                # so they can be merged into a single MultiIndex DataFrame.
                if len(tickers) > 1:
                    df.columns = pd.MultiIndex.from_product([[ticker], df.columns])
                dfs.append(df)
            except Exception as e:
                logger.error(f"Failed to download data for ticker {ticker} after retries: {e}")
                # Log error and continue to the next ticker so one failure doesn't block the job
                continue

        if not dfs:
            logger.warning(f"All tickers in batch {tickers} failed to download.")
            return pd.DataFrame()

        # Merge all dataframes along columns (outer join to align dates)
        if len(tickers) > 1:
            batch_df = pd.concat(dfs, axis=1)
        else:
            batch_df = dfs[0]

        return batch_df

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
