"""Fetches NSE corporate announcements from the official NSE public API."""

from __future__ import annotations

import datetime

import requests
from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from stocks.db.models import NSEAnnouncement, Symbol

_NSE_URL = "https://www.nseindia.com/api/corporate-announcements"
_NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
}
_KEEP_PER_SYMBOL = 50


class AnnouncementsService:
    def __init__(self, db: Session):
        self.db = db

    def get_for_symbol(self, symbol: str, limit: int = 20) -> list[dict]:
        """Return stored announcements for a symbol, newest first."""
        clean = symbol.replace(".NS", "").upper()
        rows = self.db.execute(
            select(NSEAnnouncement)
            .where(NSEAnnouncement.symbol == clean)
            .order_by(NSEAnnouncement.announcement_date.desc())
            .limit(limit)
        ).scalars().all()
        return [self._to_dict(r) for r in rows]

    def fetch_and_store(self, symbol: str) -> list[dict]:
        """Hit NSE API for a symbol and upsert announcements. Returns new items."""
        clean = symbol.replace(".NS", "").upper()
        try:
            session = requests.Session()
            # NSE requires a cookie from the homepage first
            session.get("https://www.nseindia.com", headers=_NSE_HEADERS, timeout=10)
            resp = session.get(
                _NSE_URL,
                params={"index": "equities", "symbol": clean},
                headers=_NSE_HEADERS,
                timeout=15,
            )
            resp.raise_for_status()
            items = resp.json()
        except Exception as e:
            logger.warning(f"NSE announcements fetch failed for {clean}: {e}")
            return []

        if not isinstance(items, list):
            return []

        sym_id = self.db.scalar(select(Symbol.id).where(Symbol.symbol == clean))

        new_count = 0
        for item in items[:_KEEP_PER_SYMBOL]:
            seq_id = str(item.get("seq_id", ""))
            if not seq_id:
                continue

            existing = self.db.scalar(select(NSEAnnouncement).where(NSEAnnouncement.seq_id == seq_id))
            if existing:
                continue

            ann_date = self._parse_date(item.get("an_dt") or item.get("sort_date", ""))

            row = NSEAnnouncement(
                symbol_id=sym_id,
                symbol=clean,
                seq_id=seq_id,
                announcement_date=ann_date or datetime.datetime.now(),
                subject=str(item.get("desc", ""))[:500],
                description=str(item.get("attchmntText", ""))[:2000] if item.get("attchmntText") else None,
                file_url=str(item.get("attchmntFile", ""))[:1000] if item.get("attchmntFile") else None,
            )
            self.db.add(row)
            new_count += 1

        self.db.commit()

        # Prune old rows beyond keep limit
        self._prune(clean)

        logger.info(f"NSE announcements: {new_count} new items stored for {clean}")
        return self.get_for_symbol(clean)

    def _prune(self, symbol: str) -> None:
        rows = self.db.execute(
            select(NSEAnnouncement.id)
            .where(NSEAnnouncement.symbol == symbol)
            .order_by(NSEAnnouncement.announcement_date.desc())
            .offset(_KEEP_PER_SYMBOL)
        ).scalars().all()
        if rows:
            self.db.execute(delete(NSEAnnouncement).where(NSEAnnouncement.id.in_(rows)))
            self.db.commit()

    @staticmethod
    def _parse_date(date_str: str) -> datetime.datetime | None:
        for fmt in ("%d-%b-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.datetime.strptime(date_str.strip(), fmt)
            except (ValueError, AttributeError):
                continue
        return None

    @staticmethod
    def _to_dict(r: NSEAnnouncement) -> dict:
        return {
            "id": r.id,
            "symbol": r.symbol,
            "seq_id": r.seq_id,
            "announcement_date": r.announcement_date.isoformat() if r.announcement_date else None,
            "subject": r.subject,
            "description": r.description,
            "file_url": r.file_url,
        }
