"""User-data backup/restore (V2.0 spec M8).

Exports the irreplaceable, app-created data — the trade journal, watchlists, and swing pick
notes — to a portable, versioned dict, and restores it idempotently. DB-agnostic (SQLite /
MSSQL / PG). Price/indicator data is re-syncable and intentionally excluded.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from stocks.db.models import JournalTrade, SwingPickNote, Watchlist, WatchlistItem

VERSION = 1

_TRADE_FIELDS = (
    "symbol", "setup", "side", "status", "entry_date", "entry_price", "qty",
    "stop_price", "target_price", "exit_date", "exit_price", "fees", "thesis", "mistake_tags",
)


def _iso(d: dt.date | None) -> str | None:
    return d.isoformat() if d is not None else None


def _trade_to_dict(t: JournalTrade) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for f in _TRADE_FIELDS:
        v = getattr(t, f)
        out[f] = _iso(v) if isinstance(v, dt.date) else (float(v) if isinstance(v, (int, float)) and f.endswith(("price", "qty", "fees")) else v)
    return out


def _trade_key(symbol: str, entry_date: Any, entry_price: Any, qty: Any) -> tuple:
    ed = entry_date.isoformat() if isinstance(entry_date, dt.date) else str(entry_date)
    return (symbol, ed, float(entry_price), float(qty))


def export_user_data(session: Session) -> dict[str, Any]:
    """Return a portable dict of journal trades, watchlists, and pick notes."""
    trades = session.execute(select(JournalTrade)).scalars().all()
    watchlists = session.execute(select(Watchlist)).scalars().all()
    notes = session.execute(select(SwingPickNote)).scalars().all()

    wl_out = []
    for w in watchlists:
        items = session.execute(
            select(WatchlistItem.symbol).where(WatchlistItem.watchlist_id == w.id)
        ).scalars().all()
        wl_out.append({"name": w.name, "items": list(items)})

    return {
        "version": VERSION,
        "exported_at": dt.datetime.now(dt.UTC).isoformat(),
        "journal_trades": [_trade_to_dict(t) for t in trades],
        "watchlists": wl_out,
        "swing_pick_notes": [
            {"symbol": n.symbol, "catalyst_note": n.catalyst_note} for n in notes
        ],
    }


def import_user_data(session: Session, data: dict[str, Any]) -> dict[str, int]:
    """Restore an export idempotently. Returns counts of newly-created records."""
    counts = {"journal_trades": 0, "watchlists": 0, "watchlist_items": 0, "swing_pick_notes": 0}

    # ── journal trades (dedup by symbol/entry_date/entry_price/qty) ──
    existing = {
        _trade_key(t.symbol, t.entry_date, t.entry_price, t.qty)
        for t in session.execute(select(JournalTrade)).scalars()
    }
    for td in data.get("journal_trades", []):
        key = _trade_key(td["symbol"], td["entry_date"], td["entry_price"], td["qty"])
        if key in existing:
            continue
        session.add(JournalTrade(
            symbol=td["symbol"], setup=td.get("setup", ""), side=td.get("side", "LONG"),
            status=td.get("status", "OPEN"),
            entry_date=dt.date.fromisoformat(td["entry_date"]), entry_price=td["entry_price"], qty=td["qty"],
            stop_price=td.get("stop_price"), target_price=td.get("target_price"),
            exit_date=dt.date.fromisoformat(td["exit_date"]) if td.get("exit_date") else None,
            exit_price=td.get("exit_price"), fees=td.get("fees", 0.0) or 0.0,
            thesis=td.get("thesis"), mistake_tags=td.get("mistake_tags"),
        ))
        existing.add(key)
        counts["journal_trades"] += 1

    # ── watchlists (merge by name; add missing items) ──
    for wl in data.get("watchlists", []):
        w = session.scalar(select(Watchlist).where(Watchlist.name == wl["name"]))
        if w is None:
            w = Watchlist(name=wl["name"])
            session.add(w)
            session.flush()
            counts["watchlists"] += 1
        have = set(session.execute(
            select(WatchlistItem.symbol).where(WatchlistItem.watchlist_id == w.id)
        ).scalars())
        for sym in wl.get("items", []):
            if sym not in have:
                session.add(WatchlistItem(watchlist_id=w.id, symbol=sym))
                have.add(sym)
                counts["watchlist_items"] += 1

    # ── swing pick notes (upsert by symbol PK) ──
    for nd in data.get("swing_pick_notes", []):
        note = session.get(SwingPickNote, nd["symbol"])
        if note is None:
            session.add(SwingPickNote(symbol=nd["symbol"], catalyst_note=nd.get("catalyst_note")))
            counts["swing_pick_notes"] += 1
        else:
            note.catalyst_note = nd.get("catalyst_note")

    session.commit()
    return counts
