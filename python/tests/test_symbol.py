from sqlalchemy import select

from stocks.db.models import Symbol
from stocks.services.symbol import SymbolService


def test_symbol_fallback_parsing(test_config, db_session):
    """Verifies that the local fallback EQUITY_L_ACTIVE.csv parses correctly."""
    service = SymbolService(test_config, db_session)
    symbols = service._fetch_from_fallback()

    assert len(symbols) == 5
    assert symbols[0]["symbol"] == "RELIANCE.NS"
    assert symbols[0]["company_name"] == "RELIANCE INDUSTRIES LTD"
    assert symbols[0]["isin"] == "INE002A01018"
    assert symbols[0]["series"] == "EQ"
    assert symbols[1]["symbol"] == "TCS.NS"
    assert symbols[1]["company_name"] == "TATA CONSULTANCY SERVICES LTD"


def test_symbol_database_synchronization(test_config, db_session):
    """Verifies that symbol sync writes to DB correctly and handles upserts and delistings."""
    service = SymbolService(test_config, db_session)
    symbols = service._fetch_from_fallback()

    # 1. Sync first time (should perform 5 inserts)
    synced_count = service.sync_symbols(symbols)
    assert synced_count == 5

    # Verify records exist in Database
    db_symbols = db_session.scalars(select(Symbol)).all()
    assert len(db_symbols) == 5
    assert all(s.is_active for s in db_symbols)

    # 2. Sync second time with same data (should perform 5 updates, no new duplicates)
    synced_count_repeat = service.sync_symbols(symbols)
    assert synced_count_repeat == 5

    db_symbols_repeat = db_session.scalars(select(Symbol)).all()
    assert len(db_symbols_repeat) == 5  # Total rows must remain 5

    # 3. Simulate stock delisting (remove RELIANCE.NS from the active list)
    partial_symbols = [s for s in symbols if s["symbol"] != "RELIANCE.NS"]
    synced_count_partial = service.sync_symbols(partial_symbols)
    assert synced_count_partial == 4

    # Verify in DB: RELIANCE.NS must not be deleted, but marked as is_active = False
    reliance = db_session.scalar(select(Symbol).filter_by(symbol="RELIANCE.NS"))
    assert reliance is not None
    assert reliance.is_active is False

    # TCS.NS was present, so it must remain active
    tcs = db_session.scalar(select(Symbol).filter_by(symbol="TCS.NS"))
    assert tcs is not None
    assert tcs.is_active is True
