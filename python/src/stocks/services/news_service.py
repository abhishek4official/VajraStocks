"""Fetches financial news via yfinance for NSE symbols."""

from __future__ import annotations

import datetime

import yfinance as yf
from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from stocks.db.models import NewsItem

_KEEP_PER_SYMBOL = 30


class NewsService:
    def __init__(self, db: Session):
        self.db = db

    def get_for_symbol(self, symbol: str, limit: int = 20) -> list[dict]:
        """Return cached news for a symbol, newest first."""
        clean = symbol.replace(".NS", "").upper()
        rows = self.db.execute(
            select(NewsItem)
            .where(NewsItem.symbol == clean)
            .order_by(NewsItem.published_at.desc())
            .limit(limit)
        ).scalars().all()
        return [self._to_dict(r) for r in rows]

    def fetch_and_store(self, symbol: str) -> list[dict]:
        """Fetch news from yfinance and upsert. Returns stored items."""
        clean = symbol.replace(".NS", "").upper()
        ticker_sym = f"{clean}.NS"
        try:
            news = yf.Ticker(ticker_sym).news or []
        except Exception as e:
            logger.warning(f"News fetch failed for {clean}: {e}")
            return self.get_for_symbol(clean)

        new_count = 0
        for item in news[:_KEEP_PER_SYMBOL]:
            # yfinance news structure: item["content"] dict with title, pubDate, etc.
            content = item.get("content", {}) if isinstance(item, dict) else {}
            article_id = str(item.get("id") or content.get("id") or "")[:200]
            if not article_id:
                continue

            existing = self.db.scalar(
                select(NewsItem).where(NewsItem.symbol == clean, NewsItem.article_id == article_id)
            )
            if existing:
                continue

            title = str(content.get("title") or item.get("title") or "")[:500]
            publisher = str(
                content.get("provider", {}).get("displayName") or item.get("publisher") or ""
            )[:200]
            link = str(
                content.get("canonicalUrl", {}).get("url") or item.get("link") or ""
            )[:1000]
            pub_date = self._parse_date(content.get("pubDate") or item.get("providerPublishTime"))

            self.db.add(NewsItem(
                symbol=clean,
                article_id=article_id,
                title=title,
                publisher=publisher,
                link=link,
                published_at=pub_date,
            ))
            new_count += 1

        self.db.commit()
        self._prune(clean)
        logger.info(f"News: {new_count} new items stored for {clean}")
        return self.get_for_symbol(clean)

    def _prune(self, symbol: str) -> None:
        old_ids = self.db.execute(
            select(NewsItem.id)
            .where(NewsItem.symbol == symbol)
            .order_by(NewsItem.published_at.desc())
            .offset(_KEEP_PER_SYMBOL)
        ).scalars().all()
        if old_ids:
            self.db.execute(delete(NewsItem).where(NewsItem.id.in_(old_ids)))
            self.db.commit()

    @staticmethod
    def _parse_date(val) -> datetime.datetime | None:
        if val is None:
            return None
        if isinstance(val, (int, float)):
            try:
                return datetime.datetime.fromtimestamp(val)
            except Exception:
                return None
        if isinstance(val, str):
            for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.datetime.strptime(val.strip(), fmt)
                except ValueError:
                    continue
        return None

    @staticmethod
    def _to_dict(r: NewsItem) -> dict:
        return {
            "id": r.id,
            "symbol": r.symbol,
            "title": r.title,
            "publisher": r.publisher,
            "link": r.link,
            "published_at": r.published_at.isoformat() if r.published_at else None,
        }
