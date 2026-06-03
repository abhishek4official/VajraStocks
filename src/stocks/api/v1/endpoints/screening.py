from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from stocks.api.deps import config, get_db
from stocks.services.screening import ScreeningService

router = APIRouter(prefix="/screeners", tags=["Stock Screening"])


# Pydantic Request & Response Schemas
class ScreeningParams(BaseModel):
    min_rsi: float | None = None
    max_rsi: float | None = None
    sma_20_cross: str | None = None  # 'ABOVE', 'BELOW'
    sma_50_cross: str | None = None  # 'ABOVE', 'BELOW'
    sma_200_cross: str | None = None  # 'ABOVE', 'BELOW'
    macd_trend: str | None = None  # 'BULLISH', 'BEARISH'
    ha_dir: str | None = None  # 'UP', 'DOWN'
    renko_dir: str | None = None  # 'UP', 'DOWN'
    lb_dir: str | None = None  # 'UP', 'DOWN'
    min_weekly_avg_volume: float | None = None
    volume_breakout: str | None = None  # 'ANY', '1.5X', '2.0X', '3.0X'
    only_nr7: bool = False
    only_inside_bar: bool = False
    limit: int = 2500  # No hard cap — return all matches by default


class ScreenerRowResponse(BaseModel):
    symbol_id: int
    symbol: str
    company_name: str
    last_trading_date: str
    close_price: float
    price_pct_change: float | None = None
    volume: int
    ha_close: float
    ha_direction: str
    rsi_14: float | None = None
    sma_20_cross_direction: str | None = None
    sma_50_cross_direction: str | None = None
    sma_200_cross_direction: str | None = None
    macd_trend: str | None = None
    renko_direction: str | None = None
    line_break_direction: str | None = None
    is_nr7: bool | None = None
    is_inside_bar: bool | None = None
    weekly_avg_volume: float | None = None
    volume_breakout_ratio: float | None = None

    class Config:
        from_attributes = True


@router.get("", response_model=list[ScreenerRowResponse])
def get_screening_results_get(
    min_rsi: float | None = None,
    max_rsi: float | None = None,
    sma_20_cross: str | None = None,
    sma_50_cross: str | None = None,
    sma_200_cross: str | None = None,
    macd_trend: str | None = None,
    ha_dir: str | None = None,
    renko_dir: str | None = None,
    lb_dir: str | None = None,
    min_weekly_avg_volume: float | None = None,
    volume_breakout: str | None = None,
    only_nr7: bool = False,
    only_inside_bar: bool = False,
    limit: int = 2500,
    db: Session = Depends(get_db),
):
    """Executes a high-speed screening sweep using query parameters directly against the narrow snapshot layer."""
    screening_service = ScreeningService(config, db)
    results = screening_service.query_screener(
        min_rsi=min_rsi,
        max_rsi=max_rsi,
        sma_20_cross=sma_20_cross,
        sma_50_cross=sma_50_cross,
        sma_200_cross=sma_200_cross,
        macd_trend=macd_trend,
        ha_dir=ha_dir,
        renko_dir=renko_dir,
        lb_dir=lb_dir,
        min_weekly_avg_volume=min_weekly_avg_volume,
        volume_breakout=volume_breakout,
        only_nr7=only_nr7,
        only_inside_bar=only_inside_bar,
        limit=limit,
    )

    return [
        {
            "symbol_id": r.symbol_id,
            "symbol": r.symbol,
            "company_name": r.company_name,
            "last_trading_date": r.last_trading_date.strftime("%Y-%m-%d"),
            "close_price": float(r.close_price),
            "price_pct_change": r.price_pct_change,
            "volume": int(r.volume),
            "ha_close": float(r.ha_close),
            "ha_direction": r.ha_direction,
            "rsi_14": r.rsi_14,
            "sma_20_cross_direction": r.sma_20_cross_direction,
            "sma_50_cross_direction": r.sma_50_cross_direction,
            "sma_200_cross_direction": r.sma_200_cross_direction,
            "macd_trend": r.macd_trend,
            "renko_direction": r.renko_direction,
            "line_break_direction": r.line_break_direction,
            "is_nr7": r.is_nr7,
            "is_inside_bar": r.is_inside_bar,
            "weekly_avg_volume": getattr(r, "weekly_avg_volume", None),
            "volume_breakout_ratio": getattr(r, "volume_breakout_ratio", None),
        }
        for r in results
    ]


@router.post("/run", response_model=list[ScreenerRowResponse])
def get_screening_results_post(params: ScreeningParams, db: Session = Depends(get_db)):
    """Executes a high-speed screening sweep using a POST body request directly against the snapshot layer."""
    screening_service = ScreeningService(config, db)
    results = screening_service.query_screener(
        min_rsi=params.min_rsi,
        max_rsi=params.max_rsi,
        sma_20_cross=params.sma_20_cross,
        sma_50_cross=params.sma_50_cross,
        sma_200_cross=params.sma_200_cross,
        macd_trend=params.macd_trend,
        ha_dir=params.ha_dir,
        renko_dir=params.renko_dir,
        lb_dir=params.lb_dir,
        min_weekly_avg_volume=params.min_weekly_avg_volume,
        volume_breakout=params.volume_breakout,
        only_nr7=params.only_nr7,
        only_inside_bar=params.only_inside_bar,
        limit=params.limit,
    )

    return [
        {
            "symbol_id": r.symbol_id,
            "symbol": r.symbol,
            "company_name": r.company_name,
            "last_trading_date": r.last_trading_date.strftime("%Y-%m-%d"),
            "close_price": float(r.close_price),
            "price_pct_change": r.price_pct_change,
            "volume": int(r.volume),
            "ha_close": float(r.ha_close),
            "ha_direction": r.ha_direction,
            "rsi_14": r.rsi_14,
            "sma_20_cross_direction": r.sma_20_cross_direction,
            "sma_50_cross_direction": r.sma_50_cross_direction,
            "sma_200_cross_direction": r.sma_200_cross_direction,
            "macd_trend": r.macd_trend,
            "renko_direction": r.renko_direction,
            "line_break_direction": r.line_break_direction,
            "is_nr7": r.is_nr7,
            "is_inside_bar": r.is_inside_bar,
            "weekly_avg_volume": getattr(r, "weekly_avg_volume", None),
            "volume_breakout_ratio": getattr(r, "volume_breakout_ratio", None),
        }
        for r in results
    ]
