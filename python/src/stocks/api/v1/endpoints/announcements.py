"""NSE Announcements API — corporate filings fetched from NSE's official public API."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from stocks.api.deps import get_db
from stocks.services.announcements_service import AnnouncementsService

router = APIRouter(prefix="/announcements", tags=["NSE Announcements"])


@router.get("/{symbol}")
def get_announcements(
    symbol: str,
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Return cached NSE announcements for a symbol (newest first)."""
    clean = symbol.replace(".NS", "").upper()
    svc = AnnouncementsService(db)
    return svc.get_for_symbol(clean, limit=limit)


@router.post("/{symbol}/refresh")
def refresh_announcements(symbol: str, db: Session = Depends(get_db)):
    """Fetch latest announcements from NSE API and store them."""
    clean = symbol.replace(".NS", "").upper()
    svc = AnnouncementsService(db)
    items = svc.fetch_and_store(clean)
    return {"symbol": clean, "count": len(items), "items": items}
