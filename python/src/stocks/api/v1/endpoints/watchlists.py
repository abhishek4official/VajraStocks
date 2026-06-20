"""Watchlist CRUD — backend-persisted named symbol lists."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from stocks.api.deps import get_db
from stocks.db.models import Watchlist, WatchlistItem

router = APIRouter(prefix="/watchlists", tags=["Watchlists"])


def _to_dict(wl: Watchlist) -> dict:
    return {
        "id": str(wl.id),
        "name": wl.name,
        "items": [{"symbol": item.symbol, "addedAt": item.added_at.isoformat()} for item in wl.items],
    }


class WatchlistBody(BaseModel):
    name: str


class AddSymbolBody(BaseModel):
    symbol: str


@router.get("")
def list_watchlists(db: Session = Depends(get_db)):
    wls = db.scalars(
        select(Watchlist).options(selectinload(Watchlist.items)).order_by(Watchlist.id.asc())
    ).all()
    return [_to_dict(wl) for wl in wls]


@router.post("", status_code=201)
def create_watchlist(body: WatchlistBody, db: Session = Depends(get_db)):
    wl = Watchlist(name=body.name.strip() or "Unnamed")
    db.add(wl)
    db.commit()
    db.refresh(wl)
    wl.items  # eager-load the (empty) items list
    return _to_dict(wl)


@router.put("/{watchlist_id}")
def rename_watchlist(watchlist_id: int, body: WatchlistBody, db: Session = Depends(get_db)):
    wl = db.scalar(
        select(Watchlist).options(selectinload(Watchlist.items)).where(Watchlist.id == watchlist_id)
    )
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    wl.name = body.name.strip() or wl.name
    db.commit()
    return _to_dict(wl)


@router.delete("/{watchlist_id}", status_code=204)
def delete_watchlist(watchlist_id: int, db: Session = Depends(get_db)):
    wl = db.scalar(select(Watchlist).where(Watchlist.id == watchlist_id))
    if wl:
        db.delete(wl)
        db.commit()


@router.post("/{watchlist_id}/items", status_code=201)
def add_symbol(watchlist_id: int, body: AddSymbolBody, db: Session = Depends(get_db)):
    wl = db.scalar(
        select(Watchlist).options(selectinload(Watchlist.items)).where(Watchlist.id == watchlist_id)
    )
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    # Idempotent: skip if already present
    if not any(i.symbol == body.symbol for i in wl.items):
        db.add(WatchlistItem(watchlist_id=watchlist_id, symbol=body.symbol))
        db.commit()
        db.refresh(wl)
    return _to_dict(wl)


@router.delete("/{watchlist_id}/items/{symbol:path}", status_code=204)
def remove_symbol(watchlist_id: int, symbol: str, db: Session = Depends(get_db)):
    item = db.scalar(
        select(WatchlistItem).where(
            WatchlistItem.watchlist_id == watchlist_id, WatchlistItem.symbol == symbol
        )
    )
    if item:
        db.delete(item)
        db.commit()
