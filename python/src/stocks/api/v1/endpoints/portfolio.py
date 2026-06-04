"""Portfolio endpoints — backend owns parsing, storage and all risk/MTF math."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from stocks.api.deps import get_db
from stocks.services.portfolio_service import PortfolioService

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])


@router.post("/import")
async def import_portfolio(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Imports a Zerodha holdings CSV (replaces existing holdings) and returns the composed portfolio."""
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="ignore")

    svc = PortfolioService(db)
    count = svc.import_csv(text)
    if count == 0:
        raise HTTPException(status_code=400, detail="No valid holdings found in the CSV.")
    return svc.get_portfolio()


@router.get("")
def get_portfolio(db: Session = Depends(get_db)):
    """Returns the full backend-computed portfolio (holdings + risk/MTF aggregates)."""
    return PortfolioService(db).get_portfolio()


@router.delete("")
def clear_portfolio(db: Session = Depends(get_db)):
    """Clears all imported holdings."""
    PortfolioService(db).clear()
    return {"status": "cleared"}
