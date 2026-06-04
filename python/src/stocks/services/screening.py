from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from stocks.config import Config
from stocks.db.models import (
    DailyHeikinAshi,
    DailyIndicator,
    DailyPrice,
    LineBreakLine,
    RenkoBrick,
    ScreeningSnapshot,
    Symbol,
)
from stocks.services.quant.planner import TradePlannerService
from stocks.services.settings_service import SettingsService


class ScreeningService:
    """Service to maintain the screening_snapshots table for high-performance stock sweeps."""

    def __init__(self, config: Config, db_session: Session):
        self.config = config
        self.db = db_session
        self._mtf: dict | None = None  # memoized MTF/risk thresholds

    def _mtf_thresholds(self) -> dict:
        """Loads (once) the MTF/risk thresholds from settings, memoized per service instance."""
        if self._mtf is None:
            s = SettingsService(self.db)
            self._mtf = {
                "atr_low": s.get_float("PORTFOLIO", "daily_atr_low_pct", 2.0),
                "atr_high": s.get_float("PORTFOLIO", "daily_atr_high_pct", 5.0),
                "bias_band": s.get_float("PORTFOLIO", "bias_neutral_band_pct", 2.0),
                "weekly_ema": s.get_int("PORTFOLIO", "weekly_regime_ema", 40),
            }
        return self._mtf

    def _compute_weekly_trend(self, symbol_id: int, weekly_ema_len: int) -> str | None:
        """Resamples daily closes to weekly (W-FRI) and returns UP/DOWN vs the N-week EMA.

        Uses existing daily price data — no separate weekly indicator table needed.
        Returns None when there is insufficient history.
        """
        try:
            import datetime as dt

            import pandas as pd
            import pandas_ta as ta

            # ~ weekly_ema_len*2 weeks of daily bars for a stable EMA
            cutoff = dt.date.today() - dt.timedelta(weeks=max(weekly_ema_len * 2, 60) + 10)
            rows = self.db.execute(
                select(DailyPrice.trading_date, DailyPrice.close)
                .where(DailyPrice.symbol_id == symbol_id, DailyPrice.trading_date >= cutoff)
                .order_by(DailyPrice.trading_date.asc())
            ).all()
            if len(rows) < weekly_ema_len * 5:  # ~5 trading days/week
                return None

            ser = pd.Series(
                [float(c) for _, c in rows],
                index=pd.to_datetime([d for d, _ in rows]),
            )
            weekly = ser.resample("W-FRI").last().dropna()
            if len(weekly) < weekly_ema_len:
                return None

            ema = ta.ema(weekly, length=weekly_ema_len)
            if ema is None or ema.dropna().empty:
                return None

            last_close = float(weekly.iloc[-1])
            last_ema = float(ema.dropna().iloc[-1])
            return "UP" if last_close >= last_ema else "DOWN"
        except Exception as e:
            logger.debug(f"weekly trend compute failed for symbol_id {symbol_id}: {e}")
            return None

    def refresh_snapshot_for_symbol(self, symbol_id: int, nifty_21d_return: float | None = None, commit: bool = True) -> None:
        """Compiles the latest EOD prices and derived structures to upsert the screening snapshot for a symbol."""
        try:
            symbol_obj = self.db.get(Symbol, symbol_id)
            if not symbol_obj or not symbol_obj.is_active:
                return

            # 2. Fetch latest 21 EOD prices — enough for NR7 + Inside Bar + pct change
            #    plus rolling 1W/2W/3W/4W returns (5/10/15/20 trading days back).
            prices = self.db.scalars(
                select(DailyPrice).filter_by(symbol_id=symbol_id).order_by(DailyPrice.trading_date.desc()).limit(21)
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

            # NR7: today's high-low range is the narrowest of the last 7 trading days
            is_nr7 = None
            if len(prices) >= 7:
                today_range = float(latest_price.high) - float(latest_price.low)
                prior_ranges = [float(p.high) - float(p.low) for p in prices[1:7]]
                is_nr7 = today_range < min(prior_ranges) if prior_ranges else False

            # Inside Bar: today's high < prior high AND today's low > prior low
            is_inside_bar = None
            if len(prices) >= 2:
                prev = prices[1]
                is_inside_bar = (
                    float(latest_price.high) < float(prev.high) and
                    float(latest_price.low) > float(prev.low)
                )

            # Gap Up / Gap Down: today's open vs previous close (threshold >1%)
            is_gap_up = None
            is_gap_down = None
            if len(prices) >= 2:
                prev_close = float(prices[1].close)
                today_open = float(latest_price.open)
                if prev_close > 0:
                    gap_pct = (today_open - prev_close) / prev_close
                    is_gap_up   = gap_pct >  0.01   # opened >1% above prior close
                    is_gap_down = gap_pct < -0.01   # opened >1% below prior close

            # Relative Strength vs NIFTY 50 (1-month, ~21 trading days)
            # rs_score_1m > 1.0 means outperforming NIFTY; < 1.0 means underperforming
            rs_score_1m = None
            if nifty_21d_return is not None and nifty_21d_return != 0:
                import datetime as dt
                cutoff = dt.date.today() - dt.timedelta(days=35)
                oldest_price = self.db.scalar(
                    select(DailyPrice)
                    .where(DailyPrice.symbol_id == symbol_id, DailyPrice.trading_date >= cutoff)
                    .order_by(DailyPrice.trading_date.asc())
                    .limit(1)
                )
                if oldest_price and float(oldest_price.close) > 0:
                    stock_21d_return = (close_price - float(oldest_price.close)) / float(oldest_price.close)
                    rs_score_1m = stock_21d_return / nifty_21d_return

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

            # 4. Fetch latest 2 Technical Indicator rows (2nd needed for OBV trend direction)
            ind_rows = self.db.scalars(
                select(DailyIndicator)
                .filter_by(symbol_id=symbol_id)
                .order_by(DailyIndicator.trading_date.desc())
                .limit(2)
            ).all()
            ind = ind_rows[0] if ind_rows else None
            ind_prev = ind_rows[1] if len(ind_rows) > 1 else None

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
                select(RenkoBrick).filter_by(symbol_id=symbol_id).order_by(RenkoBrick.brick_index.desc()).limit(1)
            )
            renko_direction = brick.direction if brick else None

            # 6. Fetch latest Line Break line
            lb = self.db.scalar(
                select(LineBreakLine).filter_by(symbol_id=symbol_id).order_by(LineBreakLine.line_index.desc()).limit(1)
            )
            line_break_direction = lb.direction if lb else None

            # 6b. MTF / risk fields (materialized from existing daily + weekly-resampled data)
            mtf = self._mtf_thresholds()
            atr_pct = None
            vol_class = None
            regime_bias = None
            weekly_trend = None
            mtf_confirmed = None
            adx_14_snap = None
            trend_strength_class = None
            obv_trend = None
            supertrend_dir_snap = None
            stoch_state = None

            if ind:
                atr_14 = float(ind.atr_14) if ind.atr_14 is not None else None
                if atr_14 is not None and close_price > 0:
                    atr_pct = (atr_14 / close_price) * 100.0
                    if atr_pct < mtf["atr_low"]:
                        vol_class = "LOW"
                    elif atr_pct > mtf["atr_high"]:
                        vol_class = "HIGH"
                    else:
                        vol_class = "MEDIUM"

                regime_bias, _ = TradePlannerService.compute_bias(
                    close=close_price,
                    sma_50=float(ind.sma_50) if ind.sma_50 is not None else None,
                    sma_200=float(ind.sma_200) if ind.sma_200 is not None else None,
                    ema_21=float(ind.ema_21) if ind.ema_21 is not None else None,
                    macd_histogram=float(ind.macd_histogram) if ind.macd_histogram is not None else None,
                    rsi_14=float(ind.rsi_14) if ind.rsi_14 is not None else None,
                    neutral_band_pct=mtf["bias_band"],
                    adx_14=float(ind.adx_14) if getattr(ind, "adx_14", None) is not None else None,
                    plus_di=float(ind.plus_di) if getattr(ind, "plus_di", None) is not None else None,
                    minus_di=float(ind.minus_di) if getattr(ind, "minus_di", None) is not None else None,
                )

                # ADX / trend strength
                if getattr(ind, "adx_14", None) is not None:
                    adx_14_snap = round(float(ind.adx_14), 2)
                    if adx_14_snap >= 25:
                        trend_strength_class = "STRONG"
                    elif adx_14_snap >= 15:
                        trend_strength_class = "MODERATE"
                    else:
                        trend_strength_class = "WEAK"

                # OBV trend (compare current vs previous row)
                if getattr(ind, "obv", None) is not None and ind_prev is not None and getattr(ind_prev, "obv", None) is not None:
                    curr_obv = float(ind.obv)
                    prev_obv = float(ind_prev.obv)
                    if curr_obv > prev_obv:
                        obv_trend = "UP"
                    elif curr_obv < prev_obv:
                        obv_trend = "DOWN"
                    else:
                        obv_trend = "FLAT"

                # Supertrend direction
                supertrend_dir_snap = getattr(ind, "supertrend_dir", None)

                # Stochastic state
                stoch_k_val = float(ind.stoch_k) if getattr(ind, "stoch_k", None) is not None else None
                if stoch_k_val is not None:
                    if stoch_k_val >= 80:
                        stoch_state = "OVERBOUGHT"
                    elif stoch_k_val <= 20:
                        stoch_state = "OVERSOLD"
                    else:
                        stoch_state = "NEUTRAL"

            weekly_trend = self._compute_weekly_trend(symbol_id, mtf["weekly_ema"])
            if regime_bias is not None and weekly_trend is not None:
                mtf_confirmed = (regime_bias in ("BULLISH", "VERY_BULLISH") and weekly_trend == "UP")

            # 6c. Rolling weekly returns (%) — 1W/2W/3W/4W = 5/10/15/20 trading days back.
            #     prices[] is ordered newest→oldest, so prices[n] is n trading days ago.
            def _ret(days_back: int) -> float | None:
                if len(prices) > days_back:
                    past = float(prices[days_back].close)
                    if past > 0:
                        return (close_price - past) / past * 100.0
                return None

            ret_1w = _ret(5)
            ret_2w = _ret(10)
            ret_3w = _ret(15)
            ret_4w = _ret(20)

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
                    line_break_direction=line_break_direction,
                    is_nr7=is_nr7,
                    is_inside_bar=is_inside_bar,
                    is_gap_up=is_gap_up,
                    is_gap_down=is_gap_down,
                    rs_score_1m=rs_score_1m,
                    atr_pct=atr_pct,
                    vol_class=vol_class,
                    regime_bias=regime_bias,
                    weekly_trend=weekly_trend,
                    mtf_confirmed=mtf_confirmed,
                    ret_1w=ret_1w,
                    ret_2w=ret_2w,
                    ret_3w=ret_3w,
                    ret_4w=ret_4w,
                    adx_14=adx_14_snap,
                    trend_strength_class=trend_strength_class,
                    obv_trend=obv_trend,
                    supertrend_dir=supertrend_dir_snap,
                    stoch_state=stoch_state,
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
                snapshot.is_nr7 = is_nr7
                snapshot.is_inside_bar = is_inside_bar
                snapshot.is_gap_up = is_gap_up
                snapshot.is_gap_down = is_gap_down
                snapshot.rs_score_1m = rs_score_1m
                snapshot.atr_pct = atr_pct
                snapshot.vol_class = vol_class
                snapshot.regime_bias = regime_bias
                snapshot.weekly_trend = weekly_trend
                snapshot.mtf_confirmed = mtf_confirmed
                snapshot.ret_1w = ret_1w
                snapshot.ret_2w = ret_2w
                snapshot.ret_3w = ret_3w
                snapshot.ret_4w = ret_4w
                snapshot.adx_14 = adx_14_snap
                snapshot.trend_strength_class = trend_strength_class
                snapshot.obv_trend = obv_trend
                snapshot.supertrend_dir = supertrend_dir_snap
                snapshot.stoch_state = stoch_state
            if commit:
                self.db.commit()
        except Exception as e:
            if commit:
                self.db.rollback()
            logger.error(f"Failed to refresh screening snapshot for symbol_id {symbol_id}: {e}")
            raise e

    def _get_nifty_21d_return(self) -> float | None:
        """Pre-loads the NIFTY 50 21-trading-day return for RS score computation. Returns None if not available."""
        import datetime as dt
        try:
            nifty_sym = self.db.scalar(select(Symbol).where(Symbol.symbol == "^NSEI"))
            if not nifty_sym:
                return None

            cutoff = dt.date.today() - dt.timedelta(days=35)  # 35 calendar days ≈ 25 trading days buffer
            oldest = self.db.scalar(
                select(DailyPrice)
                .where(DailyPrice.symbol_id == nifty_sym.id, DailyPrice.trading_date >= cutoff)
                .order_by(DailyPrice.trading_date.asc())
                .limit(1)
            )
            latest = self.db.scalar(
                select(DailyPrice)
                .where(DailyPrice.symbol_id == nifty_sym.id)
                .order_by(DailyPrice.trading_date.desc())
                .limit(1)
            )
            if oldest and latest and float(oldest.close) > 0:
                return (float(latest.close) - float(oldest.close)) / float(oldest.close)
        except Exception as e:
            logger.warning(f"Could not compute NIFTY 21D return: {e}")
        return None

    def refresh_all_snapshots(self) -> int:
        """Refreshes the screening snapshots for all active symbols in the database."""
        try:
            active_symbols = self.db.scalars(select(Symbol).filter_by(is_active=True)).all()
            logger.info(f"Refreshing screening snapshots for {len(active_symbols)} active symbols...")

            # Pre-load NIFTY 21-day return once — used for RS score on every symbol
            nifty_21d_return = self._get_nifty_21d_return()
            if nifty_21d_return is not None:
                logger.debug(f"NIFTY 21D return for RS scoring: {nifty_21d_return:.4f}")

            refreshed_count = 0
            for sym in active_symbols:
                try:
                    self.refresh_snapshot_for_symbol(sym.id, nifty_21d_return=nifty_21d_return, commit=False)
                    refreshed_count += 1
                except Exception as sym_err:
                    logger.error(f"Error refreshing snapshot for symbol {sym.symbol}: {sym_err}")

            self.db.commit()  # Single bulk commit at the end!
            logger.info(f"Successfully refreshed {refreshed_count} screening snapshots.")
            return refreshed_count
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to refresh all screening snapshots: {e}")
            raise e
    def query_screener(
        self,
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
        only_gap_up: bool = False,
        only_gap_down: bool = False,
        min_rs_1m: float | None = None,
        limit: int = 2500,
    ) -> list[ScreeningSnapshot]:
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
        if only_nr7:
            stmt = stmt.where(ScreeningSnapshot.is_nr7 == True)  # noqa: E712
        if only_inside_bar:
            stmt = stmt.where(ScreeningSnapshot.is_inside_bar == True)  # noqa: E712
        if only_gap_up:
            stmt = stmt.where(ScreeningSnapshot.is_gap_up == True)  # noqa: E712
        if only_gap_down:
            stmt = stmt.where(ScreeningSnapshot.is_gap_down == True)  # noqa: E712
        if min_rs_1m is not None:
            stmt = stmt.where(ScreeningSnapshot.rs_score_1m >= min_rs_1m)

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
        if only_nr7:
            symbol_ids_subq = symbol_ids_subq.where(ScreeningSnapshot.is_nr7 == True)  # noqa: E712
        if only_inside_bar:
            symbol_ids_subq = symbol_ids_subq.where(ScreeningSnapshot.is_inside_bar == True)  # noqa: E712
        if only_gap_up:
            symbol_ids_subq = symbol_ids_subq.where(ScreeningSnapshot.is_gap_up == True)  # noqa: E712
        if only_gap_down:
            symbol_ids_subq = symbol_ids_subq.where(ScreeningSnapshot.is_gap_down == True)  # noqa: E712
        if min_rs_1m is not None:
            symbol_ids_subq = symbol_ids_subq.where(ScreeningSnapshot.rs_score_1m >= min_rs_1m)

        subq = (
            select(
                DailyPrice.symbol_id,
                DailyPrice.volume,
                func.row_number()
                .over(partition_by=DailyPrice.symbol_id, order_by=DailyPrice.trading_date.desc())
                .label("rn"),
            )
            .where(DailyPrice.symbol_id.in_(symbol_ids_subq))
            .subquery()
        )

        stmt_volumes = select(subq.c.symbol_id, subq.c.volume).where(subq.c.rn <= 6)

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
