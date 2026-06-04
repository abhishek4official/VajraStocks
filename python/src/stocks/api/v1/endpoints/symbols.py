from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from stocks.api.deps import get_db
from stocks.db.models import DailyIndicator, DailyPrice, Symbol, SymbolSyncState
from stocks.services.quant.planner import TradePlannerService
from stocks.services.settings_service import SettingsService

router = APIRouter(prefix="/symbols", tags=["Symbols"])


def _resolve_symbol(symbol: str, db: Session) -> Symbol:
    """Resolves a raw/`.NS`/`^INDEX` ticker string to a Symbol row or 404s."""
    clean_sym = unquote(symbol).strip().upper()
    raw_sym = clean_sym.replace(".NS", "").replace(".BSE", "")
    if not clean_sym.endswith(".NS") and not clean_sym.startswith("^"):
        clean_sym = f"{raw_sym}.NS"
    sym = db.scalar(select(Symbol).where((Symbol.symbol == clean_sym) | (Symbol.symbol == raw_sym)))
    if not sym:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' was not found in the database.")
    return sym


# Pydantic Response Schema
class SymbolDetailResponse(BaseModel):
    id: int
    symbol: str
    company_name: str
    isin: str
    series: str
    is_active: bool
    last_successful_sync_date: str | None = None
    last_attempt_status: str | None = None
    last_error_message: str | None = None

    class Config:
        from_attributes = True


@router.get("", response_model=list[SymbolDetailResponse])
def get_all_symbols(active_only: bool = True, db: Session = Depends(get_db)):
    """Queries all registered NSE stock symbols, including their latest sync state metadata."""
    stmt = select(Symbol, SymbolSyncState).outerjoin(SymbolSyncState, Symbol.id == SymbolSyncState.symbol_id)
    if active_only:
        stmt = stmt.where(Symbol.is_active == True)

    results = db.execute(stmt).all()

    symbols_list = []
    for sym, state in results:
        symbols_list.append(
            {
                "id": sym.id,
                "symbol": sym.symbol,
                "company_name": sym.company_name,
                "isin": sym.isin,
                "series": sym.series,
                "is_active": sym.is_active,
                "last_successful_sync_date": state.last_successful_sync_date.strftime("%Y-%m-%d")
                if state and state.last_successful_sync_date
                else None,
                "last_attempt_status": state.last_attempt_status if state else None,
                "last_error_message": state.last_error_message if state else None,
            }
        )
    return symbols_list


@router.get("/{symbol}/trade-plan")
def get_trade_plan(symbol: str, db: Session = Depends(get_db)):
    """Deterministic, backend-computed trade plan + multi-factor directional bias.

    This is the single source of truth for the Trade Plan card — the frontend
    renders this payload directly and performs NO trend/plan math of its own.
    """
    sym = _resolve_symbol(symbol, db)

    # Latest 20 daily bars → close, recent swing support/resistance
    prices = db.scalars(
        select(DailyPrice)
        .filter_by(symbol_id=sym.id, granularity="1d")
        .order_by(DailyPrice.trading_date.desc())
        .limit(20)
    ).all()
    if not prices:
        raise HTTPException(status_code=404, detail=f"No price history for '{sym.symbol}'.")

    latest = prices[0]
    close = float(latest.close)
    recent_high = max(float(p.high) for p in prices)
    recent_low = min(float(p.low) for p in prices)

    ind = db.scalar(
        select(DailyIndicator)
        .filter_by(symbol_id=sym.id, granularity="1d")
        .order_by(DailyIndicator.trading_date.desc())
        .limit(1)
    )
    atr_14 = float(ind.atr_14) if ind and ind.atr_14 else close * 0.02
    sma_50 = float(ind.sma_50) if ind and ind.sma_50 is not None else None
    sma_200 = float(ind.sma_200) if ind and ind.sma_200 is not None else None
    ema_21 = float(ind.ema_21) if ind and ind.ema_21 is not None else None
    macd_hist = float(ind.macd_histogram) if ind and ind.macd_histogram is not None else None
    rsi_14 = float(ind.rsi_14) if ind and ind.rsi_14 is not None else None

    settings = SettingsService(db)
    risk_amount = settings.get_float("PORTFOLIO", "default_risk_amount", 5000.0)
    brokerage_pct = settings.get_float("PORTFOLIO", "brokerage_pct", 0.03)
    band = settings.get_float("PORTFOLIO", "bias_neutral_band_pct", 2.0)

    planner = TradePlannerService(risk_per_trade_inr=risk_amount)
    plan = planner.calculate_trade_plan(
        symbol=sym.symbol, latest_price=close, atr_14=atr_14, support=recent_low, resistance=recent_high
    )
    bias, reasons = TradePlannerService.compute_bias(
        close=close,
        sma_50=sma_50,
        sma_200=sma_200,
        ema_21=ema_21,
        macd_histogram=macd_hist,
        rsi_14=rsi_14,
        neutral_band_pct=band,
    )

    exe = plan["execution"]
    return {
        "symbol": sym.symbol.replace(".NS", ""),
        "bias": bias,
        "reasons": reasons,
        "entry": round(close, 2),
        "atr_14": round(atr_14, 2),
        "stop_loss": exe["stop_loss"],
        "target_1": exe["targets"][0],
        "target_2": exe["targets"][1],
        "entry_zone": exe["entry_zone"],
        "position_size_shares": exe["position_size_shares"],
        "risk_reward_ratio": exe["risk_reward_ratio"],
        "sma_200": round(sma_200, 2) if sma_200 is not None else None,
        "rsi_14": round(rsi_14, 1) if rsi_14 is not None else None,
        "risk_per_trade": risk_amount,
        "brokerage_pct": brokerage_pct,
        "has_indicators": ind is not None,
    }


@router.get("/{symbol}", response_model=SymbolDetailResponse)
def get_symbol_by_ticker(symbol: str, db: Session = Depends(get_db)):
    """Retrieves detailed profile metadata for a single requested stock ticker."""
    from urllib.parse import unquote
    clean_sym = unquote(symbol).strip().upper()   # handle %5ENSEI → ^NSEI
    raw_sym = clean_sym.replace(".NS", "").replace(".BSE", "")
    if not clean_sym.endswith(".NS") and not clean_sym.startswith("^"):
        clean_sym = f"{raw_sym}.NS"

    stmt = (
        select(Symbol, SymbolSyncState)
        .outerjoin(SymbolSyncState, Symbol.id == SymbolSyncState.symbol_id)
        .where((Symbol.symbol == clean_sym) | (Symbol.symbol == raw_sym))
    )

    result = db.execute(stmt).first()
    if not result:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' was not found in the database.")

    sym, state = result
    return {
        "id": sym.id,
        "symbol": sym.symbol,
        "company_name": sym.company_name,
        "isin": sym.isin,
        "series": sym.series,
        "is_active": sym.is_active,
        "last_successful_sync_date": state.last_successful_sync_date.strftime("%Y-%m-%d")
        if state and state.last_successful_sync_date
        else None,
        "last_attempt_status": state.last_attempt_status if state else None,
        "last_error_message": state.last_error_message if state else None,
    }
