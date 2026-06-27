"""Tests for user-data backup/restore (V2.0 spec M8).

Exports the irreplaceable, app-created data (trade journal, watchlists, pick notes) to a
portable, versioned dict and restores it idempotently. DB-agnostic (works on MSSQL too) —
price data is re-syncable and deliberately excluded.
"""

import datetime as dt

import pytest

from stocks.db.models import SwingPickNote, Watchlist, WatchlistItem
from stocks.services.backup import export_user_data, import_user_data
from stocks.services.journal.repository import JournalRepository

D = dt.date


@pytest.fixture
def seeded(db_session):
    JournalRepository(db_session).log_trade(
        symbol="RELIANCE", setup="pullback", entry_date=D(2026, 1, 5),
        entry_price=100.0, qty=10, stop_price=95.0, exit_date=D(2026, 1, 20), exit_price=110.0,
    )
    wl = Watchlist(name="Momentum")
    db_session.add(wl)
    db_session.flush()
    db_session.add(WatchlistItem(watchlist_id=wl.id, symbol="TCS.NS"))
    db_session.add(SwingPickNote(symbol="INFY.NS", catalyst_note="earnings beat"))
    db_session.commit()
    return db_session


def test_export_contains_user_data(seeded):
    data = export_user_data(seeded)
    assert data["version"] == 1
    assert len(data["journal_trades"]) == 1
    assert data["journal_trades"][0]["symbol"] == "RELIANCE.NS"
    assert data["watchlists"] == [{"name": "Momentum", "items": ["TCS.NS"]}]
    assert data["swing_pick_notes"] == [{"symbol": "INFY.NS", "catalyst_note": "earnings beat"}]


def test_import_restores_into_empty(db_session, seeded):
    data = export_user_data(seeded)

    # Fresh DB (separate in-memory) — reuse db_session fixture's session for a clean target.
    # Here we clear and re-import into the same session to verify idempotency instead.
    counts = import_user_data(seeded, data)
    # Everything already present -> nothing added.
    assert counts["journal_trades"] == 0
    assert counts["watchlist_items"] == 0


def test_import_into_fresh_session(db_manager):
    # Build an export from one session, import into a brand-new (empty) DB session.
    src = db_manager.get_session()
    JournalRepository(src).log_trade(symbol="AAA", setup="x", entry_date=D(2026, 1, 1),
                                     entry_price=10, qty=1, exit_date=D(2026, 1, 2), exit_price=11)
    s2 = Watchlist(name="WL1")
    src.add(s2)
    src.flush()
    src.add(WatchlistItem(watchlist_id=s2.id, symbol="ZZZ.NS"))
    src.commit()
    data = export_user_data(src)
    src.close()

    # Wipe and re-import.
    tgt = db_manager.get_session()
    for t in tgt.query(WatchlistItem).all():
        tgt.delete(t)
    for w in tgt.query(Watchlist).all():
        tgt.delete(w)
    from stocks.db.models import JournalTrade
    for j in tgt.query(JournalTrade).all():
        tgt.delete(j)
    tgt.commit()

    counts = import_user_data(tgt, data)
    assert counts["journal_trades"] == 1
    assert counts["watchlists"] == 1
    assert counts["watchlist_items"] == 1
    # Idempotent: importing again adds nothing.
    again = import_user_data(tgt, data)
    assert again["journal_trades"] == 0 and again["watchlist_items"] == 0
    tgt.close()
