"""Financial news API — articles fetched from yfinance per symbol."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from stocks.api.deps import get_db
from stocks.services.news_service import NewsService

router = APIRouter(prefix="/news", tags=["News"])


@router.get("/{symbol}")
def get_news(
    symbol: str,
    limit: int = Query(15, ge=1, le=30),
    db: Session = Depends(get_db),
):
    """Return cached news for a symbol (newest first)."""
    clean = symbol.replace(".NS", "").upper()
    svc = NewsService(db)
    return svc.get_for_symbol(clean, limit=limit)


@router.post("/{symbol}/refresh")
def refresh_news(symbol: str, db: Session = Depends(get_db)):
    """Fetch latest news from yfinance and store them."""
    clean = symbol.replace(".NS", "").upper()
    svc = NewsService(db)
    items = svc.fetch_and_store(clean)
    return {"symbol": clean, "count": len(items), "items": items}
