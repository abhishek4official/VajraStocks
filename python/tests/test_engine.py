import datetime
from unittest.mock import patch

import pandas as pd
from sqlalchemy import select

from stocks.db.models import (
    DailyIndicator,
    DailyPrice,
    ScreeningSnapshot,
    SymbolSyncState,
    SyncJob,
)
from stocks.services.downloader import DownloaderService
from stocks.services.sync_engine import SyncEngine


def mock_yfinance_download(tickers, start, end, **kwargs):
    """Generates a mock MultiIndex DataFrame for active tickers."""
    if isinstance(tickers, str):
        tickers = [tickers]
    end_date = datetime.datetime.strptime(end, "%Y-%m-%d").date()
    # Generate 3 trading days ending at end_date
    dates = [end_date - datetime.timedelta(days=2-i) for i in range(3)]

    columns = pd.MultiIndex.from_product(
        [tickers, ["Open", "High", "Low", "Close", "Adj Close", "Volume", "Dividends", "Stock Splits"]]
    )

    data = []
    for _ in dates:
        row = []
        for _ in tickers:
            # Clean EOD price data, 0 dividends, 0 splits
            row.extend([100.0, 105.0, 98.0, 102.0, 102.0, 5000, 0.0, 0.0])
        data.append(row)

    df = pd.DataFrame(data, index=pd.to_datetime(dates), columns=columns)
    return df


@patch("stocks.services.downloader.yf.download", side_effect=mock_yfinance_download)
def test_full_resumable_sync_run(mock_download, test_config, db_manager):
    """Tests full bootstrap, cold start backfill, and dynamic zero-overhead incremental updates."""
    # 1. Initialize Sync Engine
    engine = SyncEngine(test_config, db_manager)

    # 2. Run first Sync (Cold Start - Database is empty, will bootstrap and fetch 3 days for all 5 stocks)
    result = engine.run_sync()

    assert result["status"] == "SUCCESS"
    assert result["total_symbols"] == 7
    assert result["processed_symbols"] == 7
    assert result["failed_symbols"] == 0
    # 7 symbols * 3 mock days = 21 records inserted
    assert result["records_inserted"] == 21

    session = db_manager.get_session()

    # Verify that the prices were committed successfully
    total_prices = session.scalar(select(DailyPrice.id).select_from(DailyPrice).order_by(DailyPrice.id.desc()))
    assert total_prices == 21

    # Verify derived indicators and market structures are saved successfully
    total_indicators = session.query(DailyIndicator).count()
    assert total_indicators == 21

    # Verify screening snapshots are created successfully and are accurate
    total_snapshots = session.query(ScreeningSnapshot).count()
    assert total_snapshots == 7

    snapshots = session.query(ScreeningSnapshot).all()
    for snap in snapshots:
        assert snap.symbol is not None
        assert snap.close_price == 102.0
        assert snap.ha_direction == "UP"

    # Verify that the sync states are registered as successful today
    today = datetime.date.today()
    states = session.scalars(select(SymbolSyncState)).all()
    assert len(states) == 7
    assert all(s.last_successful_sync_date == today for s in states)
    assert all(s.last_attempt_status == "SUCCESS" for s in states)

    # Verify that the sync job was logged
    jobs = session.scalars(select(SyncJob)).all()
    assert len(jobs) == 1
    assert jobs[0].status == "SUCCESS"
    assert jobs[0].records_inserted == 21

    # 3. Run second Sync (Incremental / Zero-Overhead)
    # Since states say last sync date is Today, next sync start is Today + 1, which >= Today.
    # It must bypass downloading entirely and execute in zero-overhead!
    mock_download.reset_mock()

    result_incremental = engine.run_sync()

    assert result_incremental["status"] == "SUCCESS"
    assert result_incremental["total_symbols"] == 7
    # 7 symbols skipped cleanly
    assert result_incremental["processed_symbols"] == 7
    assert result_incremental["failed_symbols"] == 0
    # No new records inserted
    assert result_incremental["records_inserted"] == 0

    # Confirm that NO yfinance API request was made! (Zero overhead proven)
    mock_download.assert_not_called()


def test_fetch_batch_data_extends_end_date_inclusive(test_config, monkeypatch):
    downloader = DownloaderService(test_config)
    captured = {}

    def mocked_download(tickers, start, end, **kwargs):
        captured["start"] = start
        captured["end"] = end
        return pd.DataFrame({"Close": [100.0], "Volume": [1000]}, index=pd.to_datetime(["2026-06-01"]))

    monkeypatch.setattr("stocks.services.downloader.yf.download", mocked_download)

    downloader.fetch_batch_data(
        ["TCS.NS"],
        datetime.date(2026, 6, 1),
        datetime.date(2026, 6, 3),
    )

    assert captured["start"] == "2026-06-01"
    assert captured["end"] == "2026-06-04"
