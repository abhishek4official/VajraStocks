import datetime
from typing import Optional, List
from sqlalchemy import select, delete, func
from sqlalchemy.orm import Session
from loguru import logger
from stocks.config import Config
from stocks.db.models import (
    Symbol,
    DailyPrice,
    DailyIndicator,
    DailyHeikinAshi,
    RenkoBrick,
    LineBreakLine,
    ScreeningSnapshot
)

class ScreeningService:
    """Service to maintain the screening_snapshots table for high-performance stock sweeps."""

    def __init__(self, config: Config, db_session: Session):
        self.config = config
        self.db = db_session

    def refresh_snapshot_for_symbol(self, symbol_id: int) -> None:
        """Compiles the latest EOD prices and derived structures to upsert the screening snapshot for a symbol."""
        try:
            # 1. Fetch Symbol details
            symbol_obj = self.db.get(Symbol, symbol_id)
            if not symbol_obj or not symbol_obj.is_active:
                return

            # 2. Fetch latest 2 EOD prices to compute close and percentage change
            prices = self.db.scalars(
                select(DailyPrice)
                .filter_by(symbol_id=symbol_id)
                .order_by(DailyPrice.trading_date.desc())
                .limit(2)
            ).all()

            if not prices:
                logger.debug(f"[{symbol_obj.symbol}] No price history found. Skipping snapshot refresh.")
                return

            latest_price = prices[0]
            close_price = float(latest_price.close)
            volume = int(latest_price.volume)
            last_trading_date = latest_price.trading_date

            price_pct_change = None
            if len(prices) >= 2:
                prev_close = float(prices[1].close)
                if prev_close > 0:
                    price_pct_change = ((close_price - prev_close) / prev_close) * 100.0

            # 3. Fetch latest Heikin-Ashi candle
            ha = self.db.scalar(
                select(DailyHeikinAshi)
                .filter_by(symbol_id=symbol_id)
                .order_by(DailyHeikinAshi.trading_date.desc())
                .limit(1)
            )
            ha_close = close_price  # Fallback to standard close if no HA computed
            ha_direction = "UP"
            if ha:
                ha_close = float(ha.close)
                ha_direction = "UP" if float(ha.close) >= float(ha.open) else "DOWN"

            # 4. Fetch latest Technical Indicators
            ind = self.db.scalar(
                select(DailyIndicator)
                .filter_by(symbol_id=symbol_id)
                .order_by(DailyIndicator.trading_date.desc())
                .limit(1)
            )

            rsi_14 = None
            sma_20_cross = None
            sma_50_cross = None
            sma_200_cross = None
            macd_trend = None

            if ind:
                rsi_14 = ind.rsi_14
                
                if ind.sma_20 is not None:
                    sma_20_cross = "ABOVE" if close_price >= float(ind.sma_20) else "BELOW"
                if ind.sma_50 is not None:
                    sma_50_cross = "ABOVE" if close_price >= float(ind.sma_50) else "BELOW"
                if ind.sma_200 is not None:
                    sma_200_cross = "ABOVE" if close_price >= float(ind.sma_200) else "BELOW"
                
                if ind.macd_line is not None and ind.macd_signal is not None:
                    macd_trend = "BULLISH" if float(ind.macd_line) >= float(ind.macd_signal) else "BEARISH"

            # 5. Fetch latest Renko Brick
            brick = self.db.scalar(
                select(RenkoBrick)
                .filter_by(symbol_id=symbol_id)
                .order_by(RenkoBrick.brick_index.desc())
                .limit(1)
            )
            renko_direction = brick.direction if brick else None

            # 6. Fetch latest Line Break line
            lb = self.db.scalar(
                select(LineBreakLine)
                .filter_by(symbol_id=symbol_id)
                .order_by(LineBreakLine.line_index.desc())
                .limit(1)
            )
            line_break_direction = lb.direction if lb else None

            # 7. Upsert the ScreeningSnapshot
            snapshot = self.db.scalar(select(ScreeningSnapshot).filter_by(symbol_id=symbol_id))
            if snapshot is None:
                snapshot = ScreeningSnapshot(
                    symbol_id=symbol_id,
                    symbol=symbol_obj.symbol,
                    company_name=symbol_obj.company_name,
                    last_trading_date=last_trading_date,
                    close_price=close_price,
                    price_pct_change=price_pct_change,
                    volume=volume,
                    ha_close=ha_close,
                    ha_direction=ha_direction,
                    rsi_14=rsi_14,
                    sma_20_cross_direction=sma_20_cross,
                    sma_50_cross_direction=sma_50_cross,
                    sma_200_cross_direction=sma_200_cross,
                    macd_trend=macd_trend,
                    renko_direction=renko_direction,
                    line_break_direction=line_break_direction
                )
                self.db.add(snapshot)
            else:
                snapshot.last_trading_date = last_trading_date
                snapshot.close_price = close_price
                snapshot.price_pct_change = price_pct_change
                snapshot.volume = volume
                snapshot.ha_close = ha_close
                snapshot.ha_direction = ha_direction
                snapshot.rsi_14 = rsi_14
                snapshot.sma_20_cross_direction = sma_20_cross
                snapshot.sma_50_cross_direction = sma_50_cross
                snapshot.sma_200_cross_direction = sma_200_cross
                snapshot.macd_trend = macd_trend
                snapshot.renko_direction = renko_direction
                snapshot.line_break_direction = line_break_direction

            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to refresh screening snapshot for symbol_id {symbol_id}: {e}")
            raise e

    def refresh_all_snapshots(self) -> int:
        """Refreshes the screening snapshots for all active symbols in the database."""
        try:
            active_symbols = self.db.scalars(select(Symbol).filter_by(is_active=True)).all()
            logger.info(f"Refreshing screening snapshots for {len(active_symbols)} active symbols...")
            
            refreshed_count = 0
            for sym in active_symbols:
                self.refresh_snapshot_for_symbol(sym.id)
                refreshed_count += 1
                
            logger.info(f"Successfully refreshed {refreshed_count} screening snapshots.")
            return refreshed_count
        except Exception as e:
            logger.error(f"Failed to refresh all screening snapshots: {e}")
            raise e

    def query_screener(
        self,
        min_rsi: Optional[float] = None,
        max_rsi: Optional[float] = None,
        sma_20_cross: Optional[str] = None,
        sma_50_cross: Optional[str] = None,
        sma_200_cross: Optional[str] = None,
        macd_trend: Optional[str] = None,
        ha_dir: Optional[str] = None,
        renko_dir: Optional[str] = None,
        lb_dir: Optional[str] = None,
        min_weekly_avg_volume: Optional[float] = None,
        volume_breakout: Optional[str] = None,
        limit: int = 100
    ) -> List[ScreeningSnapshot]:
        """Runs high-speed query sweeps directly against the narrow screening_snapshots table."""
        stmt = select(ScreeningSnapshot)
        
        if min_rsi is not None:
            stmt = stmt.where(ScreeningSnapshot.rsi_14 >= min_rsi)
        if max_rsi is not None:
            stmt = stmt.where(ScreeningSnapshot.rsi_14 <= max_rsi)
        if sma_20_cross is not None:
            stmt = stmt.where(ScreeningSnapshot.sma_20_cross_direction == sma_20_cross.upper())
        if sma_50_cross is not None:
            stmt = stmt.where(ScreeningSnapshot.sma_50_cross_direction == sma_50_cross.upper())
        if sma_200_cross is not None:
            stmt = stmt.where(ScreeningSnapshot.sma_200_cross_direction == sma_200_cross.upper())
        if macd_trend is not None:
            stmt = stmt.where(ScreeningSnapshot.macd_trend == macd_trend.upper())
        if ha_dir is not None:
            stmt = stmt.where(ScreeningSnapshot.ha_direction == ha_dir.upper())
        if renko_dir is not None:
            stmt = stmt.where(ScreeningSnapshot.renko_direction == renko_dir.upper())
        if lb_dir is not None:
            stmt = stmt.where(ScreeningSnapshot.line_break_direction == lb_dir.upper())
            
        stmt = stmt.order_by(ScreeningSnapshot.symbol.asc())
        
        # Optimize: if no volume filters are applied, we can apply SQL limit immediately
        has_volume_filters = min_weekly_avg_volume is not None or (
            volume_breakout is not None and volume_breakout.upper() != "ANY"
        )
        if not has_volume_filters:
            stmt = stmt.limit(limit)
            
        base_results = list(self.db.scalars(stmt).all())
        if not base_results:
            return []
            
        # 1. Fetch volumes of the last 6 days for the matched symbol IDs in a single batch.
        # We use a nested subquery on ScreeningSnapshot to avoid SQL Server parameter limits (max 2100).
        symbol_ids_subq = select(ScreeningSnapshot.symbol_id)
        if min_rsi is not None:
            symbol_ids_subq = symbol_ids_subq.where(ScreeningSnapshot.rsi_14 >= min_rsi)
        if max_rsi is not None:
            symbol_ids_subq = symbol_ids_subq.where(ScreeningSnapshot.rsi_14 <= max_rsi)
        if sma_20_cross is not None:
            symbol_ids_subq = symbol_ids_subq.where(ScreeningSnapshot.sma_20_cross_direction == sma_20_cross.upper())
        if sma_50_cross is not None:
            symbol_ids_subq = symbol_ids_subq.where(ScreeningSnapshot.sma_50_cross_direction == sma_50_cross.upper())
        if sma_200_cross is not None:
            symbol_ids_subq = symbol_ids_subq.where(ScreeningSnapshot.sma_200_cross_direction == sma_200_cross.upper())
        if macd_trend is not None:
            symbol_ids_subq = symbol_ids_subq.where(ScreeningSnapshot.macd_trend == macd_trend.upper())
        if ha_dir is not None:
            symbol_ids_subq = symbol_ids_subq.where(ScreeningSnapshot.ha_direction == ha_dir.upper())
        if renko_dir is not None:
            symbol_ids_subq = symbol_ids_subq.where(ScreeningSnapshot.renko_direction == renko_dir.upper())
        if lb_dir is not None:
            symbol_ids_subq = symbol_ids_subq.where(ScreeningSnapshot.line_break_direction == lb_dir.upper())
            
        subq = select(
            DailyPrice.symbol_id,
            DailyPrice.volume,
            func.row_number().over(
                partition_by=DailyPrice.symbol_id,
                order_by=DailyPrice.trading_date.desc()
            ).label("rn")
        ).where(DailyPrice.symbol_id.in_(symbol_ids_subq)).subquery()
        
        stmt_volumes = select(
            subq.c.symbol_id,
            subq.c.volume
        ).where(subq.c.rn <= 6)
        
        volume_rows = self.db.execute(stmt_volumes).all()
        
        # 2. Group by symbol_id
        from collections import defaultdict
        volumes_by_symbol = defaultdict(list)
        for sym_id, vol in volume_rows:
            volumes_by_symbol[sym_id].append(int(vol))
            
        # 3. Calculate weekly avg volume and breakout ratio, then apply memory filters
        filtered_results = []
        for snapshot in base_results:
            sym_id = snapshot.symbol_id
            vols = volumes_by_symbol.get(sym_id, [])
            
            latest_volume = vols[0] if len(vols) >= 1 else int(snapshot.volume)
            preceding_vols = vols[1:6] if len(vols) > 1 else []
            
            if preceding_vols:
                weekly_avg_volume = sum(preceding_vols) / len(preceding_vols)
            else:
                weekly_avg_volume = float(latest_volume)
                
            breakout_ratio = (latest_volume / weekly_avg_volume) if weekly_avg_volume > 0 else 1.0
            
            # Attach dynamic calculated attributes
            snapshot.weekly_avg_volume = weekly_avg_volume
            snapshot.volume_breakout_ratio = breakout_ratio
            
            # Apply memory filtering criteria
            keep = True
            if min_weekly_avg_volume is not None:
                if weekly_avg_volume < min_weekly_avg_volume:
                    keep = False
                    
            if keep and volume_breakout is not None:
                bo_upper = volume_breakout.upper()
                if bo_upper == "1.5X":
                    if breakout_ratio < 1.5:
                        keep = False
                elif bo_upper == "2.0X":
                    if breakout_ratio < 2.0:
                        keep = False
                elif bo_upper == "3.0X":
                    if breakout_ratio < 3.0:
                        keep = False
                        
            if keep:
                filtered_results.append(snapshot)
                
        # 4. Limit results if volume filters were applied
        if has_volume_filters:
            filtered_results = filtered_results[:limit]
            
        return filtered_results
