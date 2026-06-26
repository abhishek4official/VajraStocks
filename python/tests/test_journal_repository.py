"""Tests for the trade-journal repository (V2.0 spec M3)."""

import datetime as dt

import pytest

from stocks.services.journal.repository import JournalRepository

D = dt.date


@pytest.fixture
def repo(db_session):
    return JournalRepository(db_session)


def test_log_open_trade(repo):
    t = repo.log_trade(symbol="RELIANCE", setup="pullback", entry_date=D(2026, 1, 5),
                       entry_price=1200.0, qty=10, stop_price=1150.0, target_price=1320.0)
    assert t.id is not None
    assert t.symbol == "RELIANCE.NS"   # normalized
    assert t.status == "OPEN"
    assert t.exit_price is None


def test_log_closed_directly(repo):
    t = repo.log_trade(symbol="TCS", setup="breakout", entry_date=D(2026, 1, 5),
                       entry_price=100.0, qty=10, stop_price=95.0,
                       exit_date=D(2026, 1, 20), exit_price=110.0)
    assert t.status == "CLOSED"


def test_log_then_close(repo):
    t = repo.log_trade(symbol="INFY", setup="pullback", entry_date=D(2026, 1, 5),
                       entry_price=100.0, qty=10, stop_price=95.0)
    assert t.status == "OPEN"
    closed = repo.close_trade(t.id, exit_date=D(2026, 1, 20), exit_price=112.0, mistake_tags="early_exit")
    assert closed.status == "CLOSED"
    assert closed.exit_price == 112.0
    assert closed.mistake_tags == "early_exit"


def test_list_filters(repo):
    repo.log_trade(symbol="AAA", setup="x", entry_date=D(2026, 1, 1), entry_price=10, qty=1)
    repo.log_trade(symbol="BBB", setup="x", entry_date=D(2026, 1, 1), entry_price=10, qty=1,
                   exit_date=D(2026, 1, 2), exit_price=11)
    assert len(repo.list_trades()) == 2
    assert len(repo.list_trades(status="OPEN")) == 1
    assert repo.list_trades(symbol="AAA")[0].symbol == "AAA.NS"


def test_delete(repo):
    t = repo.log_trade(symbol="ZZZ", setup="x", entry_date=D(2026, 1, 1), entry_price=10, qty=1)
    assert repo.delete(t.id) is True
    assert repo.get(t.id) is None


def test_review_by_setup(repo):
    # Two closed pullback trades: a +2R winner and a -0.8R loser.
    repo.log_trade(symbol="A", setup="pullback", entry_date=D(2026, 1, 1), entry_price=100, qty=10,
                   stop_price=95, exit_date=D(2026, 1, 5), exit_price=110)
    repo.log_trade(symbol="B", setup="pullback", entry_date=D(2026, 1, 1), entry_price=100, qty=10,
                   stop_price=95, exit_date=D(2026, 1, 5), exit_price=96)
    # An open trade must be excluded from the review.
    repo.log_trade(symbol="C", setup="pullback", entry_date=D(2026, 1, 1), entry_price=100, qty=10, stop_price=95)

    review = repo.review()
    pb = review["pullback"]
    assert pb.trades == 2
    assert pb.wins == 1
    assert pb.win_rate == pytest.approx(0.5)
    assert pb.avg_r == pytest.approx(0.6)
    assert pb.total_pnl == pytest.approx(60.0)
