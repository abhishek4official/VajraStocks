import datetime
from unittest.mock import MagicMock, patch
import pytest
from stocks.services.scheduler import check_and_run_sync
from stocks.db.models import SyncJob


@pytest.mark.anyio
async def test_scheduler_triggers_sync_when_missed(db_manager):
    # Setup - Database has no SyncJobs at all (so today's sync is missed)

    # We patch SyncEngine.run_sync to see if it gets called
    with patch("stocks.services.scheduler.SyncEngine") as mock_engine_cls:
        mock_engine = MagicMock()
        mock_engine_cls.return_value = mock_engine

        await check_and_run_sync(db_manager)

        # Verify it triggered sync
        mock_engine.run_sync.assert_called_once()


@pytest.mark.anyio
async def test_scheduler_does_not_trigger_sync_when_already_run(db_manager):
    # Setup - Database already has a successful SyncJob for today
    session = db_manager.get_session()

    from stocks.services.scheduler import get_latest_eod_threshold
    threshold = get_latest_eod_threshold(datetime.datetime.now())

    # Seed a successful job starting at/after the threshold
    job = SyncJob(
        run_id="test-run-id",
        start_time=threshold + datetime.timedelta(minutes=10),
        status="SUCCESS",
        total_symbols=1,
        processed_symbols=1,
        failed_symbols=0,
        records_inserted=10
    )
    session.add(job)
    session.commit()
    session.close()

    # Patch SyncEngine to ensure run_sync is NOT called
    with patch("stocks.services.scheduler.SyncEngine") as mock_engine_cls:
        mock_engine = MagicMock()
        mock_engine_cls.return_value = mock_engine

        await check_and_run_sync(db_manager)

        # Verify it did not trigger sync
        mock_engine.run_sync.assert_not_called()


@pytest.mark.anyio
async def test_scheduler_does_not_trigger_sync_when_partial_run(db_manager):
    # Setup - Database already has a partial SyncJob for today
    session = db_manager.get_session()

    from stocks.services.scheduler import get_latest_eod_threshold
    threshold = get_latest_eod_threshold(datetime.datetime.now())

    # Seed a partial job starting at/after the threshold
    job = SyncJob(
        run_id="test-run-id-partial",
        start_time=threshold + datetime.timedelta(minutes=15),
        status="PARTIAL",
        total_symbols=10,
        processed_symbols=8,
        failed_symbols=2,
        records_inserted=80
    )
    session.add(job)
    session.commit()
    session.close()

    # Patch SyncEngine to ensure run_sync is NOT called
    with patch("stocks.services.scheduler.SyncEngine") as mock_engine_cls:
        mock_engine = MagicMock()
        mock_engine_cls.return_value = mock_engine

        await check_and_run_sync(db_manager)

        # Verify it did not trigger sync
        mock_engine.run_sync.assert_not_called()


def test_get_latest_eod_threshold():
    from stocks.services.scheduler import get_latest_eod_threshold

    # Thursday after 5:15 AM -> Thursday 5:15 AM
    dt1 = datetime.datetime(2026, 6, 4, 6, 0, 0)
    assert get_latest_eod_threshold(dt1) == datetime.datetime(2026, 6, 4, 5, 15, 0)

    # Thursday before 5:15 AM -> Wednesday 5:15 AM
    dt2 = datetime.datetime(2026, 6, 4, 4, 30, 0)
    assert get_latest_eod_threshold(dt2) == datetime.datetime(2026, 6, 3, 5, 15, 0)

    # Sunday after 5:15 AM -> Sunday 5:15 AM
    dt3 = datetime.datetime(2026, 6, 7, 12, 0, 0)
    assert get_latest_eod_threshold(dt3) == datetime.datetime(2026, 6, 7, 5, 15, 0)
