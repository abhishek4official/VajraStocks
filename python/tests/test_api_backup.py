"""API tests for backup export/import (V2.0 spec M8)."""

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from stocks.api.deps import get_db
from stocks.api.main import app
from stocks.services.journal.repository import JournalRepository


@pytest.fixture
def api_client(db_session):
    JournalRepository(db_session).log_trade(
        symbol="RELIANCE", setup="pullback", entry_date=dt.date(2026, 1, 5),
        entry_price=100.0, qty=10, stop_price=95.0, exit_date=dt.date(2026, 1, 20), exit_price=110.0,
    )
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_export_then_import_roundtrip(api_client):
    data = api_client.get("/api/v1/backup/export").json()
    assert data["version"] == 1
    assert len(data["journal_trades"]) == 1

    # Re-importing the same export is idempotent (nothing new).
    counts = api_client.post("/api/v1/backup/import", json=data).json()
    assert counts["journal_trades"] == 0
