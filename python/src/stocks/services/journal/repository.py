"""Trade-journal repository (V2.0 spec M3): log trades, close them, list, and auto-review."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from stocks.db.models import JournalTrade
from stocks.services.journal.analytics import ClosedTrade, SetupStats, review_by_setup


def _normalize(symbol: str) -> str:
    s = symbol.strip().upper()
    if not s.endswith(".NS") and not s.startswith("^"):
        s = f"{s}.NS"
    return s


class JournalRepository:
    def __init__(self, session: Session):
        self.session = session

    def log_trade(
        self,
        *,
        symbol: str,
        entry_date: dt.date,
        entry_price: float,
        qty: float,
        setup: str = "",
        side: str = "LONG",
        stop_price: float | None = None,
        target_price: float | None = None,
        thesis: str | None = None,
        exit_date: dt.date | None = None,
        exit_price: float | None = None,
        fees: float = 0.0,
    ) -> JournalTrade:
        """Create a journal trade. Status is CLOSED if an exit is supplied, else OPEN."""
        trade = JournalTrade(
            symbol=_normalize(symbol),
            setup=setup,
            side=side.upper(),
            status="CLOSED" if exit_price is not None else "OPEN",
            entry_date=entry_date,
            entry_price=entry_price,
            qty=qty,
            stop_price=stop_price,
            target_price=target_price,
            exit_date=exit_date,
            exit_price=exit_price,
            fees=fees,
            thesis=thesis,
        )
        self.session.add(trade)
        self.session.commit()
        return trade

    def close_trade(
        self,
        trade_id: int,
        *,
        exit_date: dt.date,
        exit_price: float,
        fees: float | None = None,
        mistake_tags: str | None = None,
    ) -> JournalTrade:
        """Record the exit for an open trade and mark it CLOSED."""
        trade = self.session.get(JournalTrade, trade_id)
        if trade is None:
            raise ValueError(f"No journal trade {trade_id}")
        trade.exit_date = exit_date
        trade.exit_price = exit_price
        trade.status = "CLOSED"
        if fees is not None:
            trade.fees = fees
        if mistake_tags is not None:
            trade.mistake_tags = mistake_tags
        self.session.commit()
        return trade

    def get(self, trade_id: int) -> JournalTrade | None:
        return self.session.get(JournalTrade, trade_id)

    def list_trades(self, symbol: str | None = None, status: str | None = None) -> list[JournalTrade]:
        stmt = select(JournalTrade)
        if symbol is not None:
            stmt = stmt.where(JournalTrade.symbol == _normalize(symbol))
        if status is not None:
            stmt = stmt.where(JournalTrade.status == status.upper())
        stmt = stmt.order_by(JournalTrade.entry_date.desc(), JournalTrade.id.desc())
        return list(self.session.execute(stmt).scalars())

    def delete(self, trade_id: int) -> bool:
        trade = self.session.get(JournalTrade, trade_id)
        if trade is None:
            return False
        self.session.delete(trade)
        self.session.commit()
        return True

    def review(self) -> dict[str, SetupStats]:
        """Per-setup auto-review over CLOSED trades (win rate, expectancy-in-R, P&L)."""
        closed = self.session.execute(
            select(JournalTrade).where(
                JournalTrade.status == "CLOSED", JournalTrade.exit_price.is_not(None)
            )
        ).scalars()
        records = [
            ClosedTrade(
                setup=t.setup or "(untagged)",
                side=t.side,
                entry=float(t.entry_price),
                # No stop -> use entry so risk is non-positive -> R is undefined (handled).
                stop=float(t.stop_price) if t.stop_price is not None else float(t.entry_price),
                exit=float(t.exit_price),
                qty=float(t.qty),
                fees=float(t.fees or 0.0),
            )
            for t in closed
        ]
        return review_by_setup(records)
