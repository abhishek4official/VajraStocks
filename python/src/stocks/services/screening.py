from collections import defaultdict

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

    # MSSQL limits total parameters per statement to 2100; keep IN lists comfortably below that.
    _MSSQL_IN_LIMIT = 2000

    def __init__(self, config: Config, db_session: Session):
        self.config = config
        self.db = db_session
        self._mtf: dict | None = None  # memoized MTF/risk thresholds

    @staticmethod
    def _id_chunks(ids: list[int], size: int = _MSSQL_IN_LIMIT):
        """Yield successive slices of *ids* of at most *size* each."""
        for i in range(0, len(ids), size):
            yield ids[i : i + size]

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

    def _compute_weekly_trend(self, symbol_id: int, weekly_ema_len: int, *, rows=None) -> str | None:
        """Resamples daily closes to weekly (W-FRI) and returns UP/DOWN vs the N-week EMA.

        Uses existing daily price data — no separate weekly indicator table needed.
        Returns None when there is insufficient history.
        Pass pre-loaded `rows` (list of (trading_date, close) tuples, asc order) to skip
        the DB query — used by refresh_all_snapshots to avoid N+1 queries.
        """
        try:
            import pandas as pd
            import pandas_ta as ta

            if rows is None:
                import datetime as dt
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

    def refresh_snapshot_for_symbol(
        self,
        symbol_id: int,
        nifty_21d_return: float | None = None,
        commit: bool = True,
        *,
        _prefetch: dict | None = None,
    ) -> None:
        """Compiles the latest EOD prices and derived structures to upsert the screening snapshot for a symbol.

        Pass `_prefetch` (built by refresh_all_snapshots) to skip all per-symbol DB queries
        and read from pre-loaded bulk data instead, eliminating the N+1 pattern.
        """
        try:
            symbol_obj = _prefetch["symbol"] if _prefetch else self.db.get(Symbol, symbol_id)
            if not symbol_obj or not symbol_obj.is_active:
                return

            # 2. Fetch latest 21 EOD prices — enough for NR7 + Inside Bar + pct change
            #    plus rolling 1W/2W/3W/4W returns (5/10/15/20 trading days back).
            prices = _prefetch["prices"] if _prefetch else self.db.scalars(
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
                if _prefetch:
                    oldest_price = _prefetch.get("rs_oldest")
                else:
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
            ha = _prefetch["ha"] if _prefetch else self.db.scalar(
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

            # 4. Fetch latest 22 Technical Indicator rows
            #    2nd needed for OBV trend; up to 22nd needed for 20-day crossover window
            ind_rows = _prefetch["ind_rows"] if _prefetch else self.db.scalars(
                select(DailyIndicator)
                .filter_by(symbol_id=symbol_id)
                .order_by(DailyIndicator.trading_date.desc())
                .limit(22)
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

            # CMF snapshot fields
            cmf_20_snap = float(ind.cmf_20) if ind and getattr(ind, "cmf_20", None) is not None else None
            cmf_20_prev_snap = float(ind_prev.cmf_20) if ind_prev and getattr(ind_prev, "cmf_20", None) is not None else None
            cmf_crossed_above_zero = (
                cmf_20_snap is not None and cmf_20_snap > 0 and
                cmf_20_prev_snap is not None and cmf_20_prev_snap <= 0
            )

            # StochRSI snapshot fields
            stochrsi_k_snap = float(ind.stochrsi_k) if ind and getattr(ind, "stochrsi_k", None) is not None else None
            stochrsi_d_snap = float(ind.stochrsi_d) if ind and getattr(ind, "stochrsi_d", None) is not None else None

            stochrsi_zone = None
            if stochrsi_k_snap is not None:
                if stochrsi_k_snap >= 80:
                    stochrsi_zone = "OVERBOUGHT"
                elif stochrsi_k_snap >= 50:
                    stochrsi_zone = "BULLISH"
                elif stochrsi_k_snap >= 20:
                    stochrsi_zone = "BEARISH"
                else:
                    stochrsi_zone = "OVERSOLD"

            # Crossover days-ago: scan indicator rows (newest → oldest)
            stochrsi_bullish_xover_days_ago = None
            stochrsi_bearish_xover_days_ago = None
            for i, row in enumerate(ind_rows):
                if stochrsi_bullish_xover_days_ago is None and getattr(row, "stochrsi_bullish_xover", None):
                    stochrsi_bullish_xover_days_ago = i
                if stochrsi_bearish_xover_days_ago is None and getattr(row, "stochrsi_bearish_xover", None):
                    stochrsi_bearish_xover_days_ago = i

            # MA / price crossover recency — build date-keyed price dict for close lookups
            prices_by_date = {p.trading_date: float(p.close) for p in prices}

            def _xover(above_fn) -> tuple[int | None, int | None]:
                """Scan ind_rows newest→oldest; return (days_since_bull, days_since_bear)."""
                bull = bear = None
                for _i in range(len(ind_rows) - 1):
                    if _i >= 20:
                        break
                    curr = above_fn(ind_rows[_i])
                    prev = above_fn(ind_rows[_i + 1])
                    if curr is None or prev is None:
                        continue
                    if bull is None and curr and not prev:
                        bull = _i
                    if bear is None and not curr and prev:
                        bear = _i
                    if bull is not None and bear is not None:
                        break
                return bull, bear

            def _above_price_sma20(r):
                p = prices_by_date.get(r.trading_date)
                return (p > float(r.sma_20)) if (p and r.sma_20 is not None) else None

            def _above_price_sma50(r):
                p = prices_by_date.get(r.trading_date)
                return (p > float(r.sma_50)) if (p and r.sma_50 is not None) else None

            def _above_price_ema20(r):
                p = prices_by_date.get(r.trading_date)
                return (p > float(r.ema_20)) if (p and getattr(r, "ema_20", None) is not None) else None

            def _above_ema9_ema20(r):
                if getattr(r, "ema_9", None) is None or getattr(r, "ema_20", None) is None:
                    return None
                return float(r.ema_9) > float(r.ema_20)

            def _above_sma20_sma50(r):
                if r.sma_20 is None or r.sma_50 is None:
                    return None
                return float(r.sma_20) > float(r.sma_50)

            def _above_macd(r):
                if r.macd_line is None or r.macd_signal is None:
                    return None
                return float(r.macd_line) > float(r.macd_signal)

            def _above_cmf_zero(r):
                if getattr(r, "cmf_20", None) is None:
                    return None
                return float(r.cmf_20) > 0.0

            days_since_price_sma20_bull, _ = _xover(_above_price_sma20)
            days_since_price_sma50_bull, _ = _xover(_above_price_sma50)
            days_since_price_ema20_bull, _ = _xover(_above_price_ema20)
            days_since_ema9_ema20_bull, days_since_ema9_ema20_bear = _xover(_above_ema9_ema20)
            days_since_sma20_sma50_bull, _ = _xover(_above_sma20_sma50)
            days_since_macd_bull, days_since_macd_bear = _xover(_above_macd)
            days_since_cmf_bull, days_since_cmf_bear = _xover(_above_cmf_zero)

            # Continuous crossover metrics (current-day values only)
            ema9_ema20_spread = None
            macd_histogram_slope = None
            macd_above_zero = None
            cmf_slope_5d = None
            if ind:
                if getattr(ind, "ema_9", None) is not None and getattr(ind, "ema_20", None) is not None and close_price > 0:
                    ema9_ema20_spread = round((float(ind.ema_9) - float(ind.ema_20)) / close_price * 100, 4)
                if ind.macd_line is not None:
                    macd_above_zero = float(ind.macd_line) > 0
                # 3-day histogram slope: need row at index 3
                if ind.macd_histogram is not None and len(ind_rows) > 3 and ind_rows[3].macd_histogram is not None:
                    macd_histogram_slope = round((float(ind.macd_histogram) - float(ind_rows[3].macd_histogram)) / 3, 6)
                # 5-day CMF slope: need row at index 5
                if getattr(ind, "cmf_20", None) is not None and len(ind_rows) > 5 and getattr(ind_rows[5], "cmf_20", None) is not None:
                    cmf_slope_5d = round(float(ind.cmf_20) - float(ind_rows[5].cmf_20), 4)

            # 5. Fetch latest Renko Brick
            brick = _prefetch["brick"] if _prefetch else self.db.scalar(
                select(RenkoBrick).filter_by(symbol_id=symbol_id).order_by(RenkoBrick.brick_index.desc()).limit(1)
            )
            renko_direction = brick.direction if brick else None

            # 6. Fetch latest Line Break line
            lb = _prefetch["lb"] if _prefetch else self.db.scalar(
                select(LineBreakLine).filter_by(symbol_id=symbol_id).order_by(LineBreakLine.line_index.desc()).limit(1)
            )
            line_break_direction = lb.direction if lb else None

            # 6b. MTF / risk fields
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
            composite_score = None
            trend_score_val = None
            volume_score_val = None
            rs_score_val = None
            momentum_score_val = None
            macd_hist_prev = None

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

                # OBV trend (compare current vs previous row)
                if getattr(ind, "obv", None) is not None and ind_prev is not None and getattr(ind_prev, "obv", None) is not None:
                    curr_obv = float(ind.obv)
                    prev_obv = float(ind_prev.obv)
                    obv_trend = "UP" if curr_obv > prev_obv else ("DOWN" if curr_obv < prev_obv else "FLAT")

                # Supertrend direction
                supertrend_dir_snap = getattr(ind, "supertrend_dir", None)

                # Stochastic state
                stoch_k_val = float(ind.stoch_k) if getattr(ind, "stoch_k", None) is not None else None
                if stoch_k_val is not None:
                    stoch_state = "OVERBOUGHT" if stoch_k_val >= 80 else ("OVERSOLD" if stoch_k_val <= 20 else "NEUTRAL")

                # ADX trend strength class
                if getattr(ind, "adx_14", None) is not None:
                    adx_14_snap = round(float(ind.adx_14), 2)
                    trend_strength_class = "STRONG" if adx_14_snap >= 25 else ("MODERATE" if adx_14_snap >= 15 else "WEAK")

                # MACD histogram prev (for growing detection)
                macd_hist_prev = float(ind_prev.macd_histogram) if ind_prev and ind_prev.macd_histogram is not None else None

            # 6b-ii. Composite score — runs after rolling returns are known
            # (we compute returns first below, then call composite scorer)

            weekly_trend = (
                _prefetch.get("weekly_trend") if _prefetch
                else self._compute_weekly_trend(symbol_id, mtf["weekly_ema"])
            )

            # 6c. Rolling weekly returns (%) — 1W/2W/3W/4W = 5/10/15/20 trading days back.
            def _ret(days_back: int) -> float | None:
                if len(prices) > days_back:
                    past = float(prices[days_back].close)
                    if past > 0:
                        return (close_price - past) / past * 100.0
                return None

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

            # 6c-ii. Avg traded value (price×volume) and volume breakout ratio
            avg_traded_value = None
            volume_breakout_ratio = None
            if len(prices) >= 2:
                past_prices = prices[1:21]  # exclude today
                vols = [float(p.volume) for p in past_prices]
                if vols:
                    traded_vals = [float(p.close) * float(p.volume) for p in past_prices]
                    avg_traded_value = round(sum(traded_vals) / len(traded_vals), 0)
                    avg_vol = sum(vols) / len(vols)
                    if avg_vol > 0:
                        volume_breakout_ratio = round(volume / avg_vol, 2)

            # 6d. Composite scorer — now has all inputs
            cmf_score_val = None
            breakout_score_val = None
            if ind:
                from stocks.services.quant.composite_scorer import compute_composite
                cs = compute_composite(
                    close=close_price,
                    ema_20=float(ind.ema_20) if getattr(ind, "ema_20", None) is not None else None,
                    sma_50=float(ind.sma_50) if ind.sma_50 is not None else None,
                    sma_200=float(ind.sma_200) if ind.sma_200 is not None else None,
                    ema_21=float(ind.ema_21) if ind.ema_21 is not None else None,
                    adx_14=adx_14_snap,
                    plus_di=float(ind.plus_di) if getattr(ind, "plus_di", None) is not None else None,
                    minus_di=float(ind.minus_di) if getattr(ind, "minus_di", None) is not None else None,
                    volume_breakout_ratio=volume_breakout_ratio,
                    obv_trend=obv_trend,
                    delivery_pct=None,
                    rs_score_1m=rs_score_1m,
                    ret_1w=ret_1w,
                    ret_4w=ret_4w,
                    macd_histogram=float(ind.macd_histogram) if ind.macd_histogram is not None else None,
                    macd_histogram_prev=macd_hist_prev,
                    stochrsi_k=stochrsi_k_snap,
                    stochrsi_d=stochrsi_d_snap,
                    stochrsi_bullish_xover_days_ago=stochrsi_bullish_xover_days_ago,
                    stochrsi_bearish_xover_days_ago=stochrsi_bearish_xover_days_ago,
                    cmf_20=cmf_20_snap,
                    cmf_20_prev=cmf_20_prev_snap,
                    supertrend_dir=supertrend_dir_snap,
                    is_nr7=is_nr7,
                    is_inside_bar=is_inside_bar,
                    is_gap_up=is_gap_up,
                    renko_dir=renko_direction,
                    line_break_dir=line_break_direction,
                )
                regime_bias = cs.bias
                composite_score = cs.composite_score
                trend_score_val = cs.trend_score
                volume_score_val = cs.volume_score
                rs_score_val = cs.rs_score
                momentum_score_val = cs.momentum_score
                cmf_score_val = cs.cmf_score
                breakout_score_val = cs.breakout_score

            if regime_bias is not None and weekly_trend is not None:
                mtf_confirmed = (regime_bias in ("BULLISH", "VERY_BULLISH") and weekly_trend == "UP")

            # 7. Upsert the ScreeningSnapshot
            snapshot = _prefetch.get("snapshot") if _prefetch else self.db.scalar(
                select(ScreeningSnapshot).filter_by(symbol_id=symbol_id)
            )
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
                    avg_traded_value=avg_traded_value,
                    volume_breakout_ratio=volume_breakout_ratio,
                    composite_score=composite_score,
                    trend_score_val=trend_score_val,
                    volume_score_val=volume_score_val,
                    rs_score_val=rs_score_val,
                    momentum_score_val=momentum_score_val,
                    cmf_score_val=cmf_score_val,
                    breakout_score_val=breakout_score_val,
                    cmf_20=cmf_20_snap,
                    cmf_20_prev=cmf_20_prev_snap,
                    cmf_crossed_above_zero=cmf_crossed_above_zero,
                    stochrsi_k=stochrsi_k_snap,
                    stochrsi_d=stochrsi_d_snap,
                    stochrsi_zone=stochrsi_zone,
                    stochrsi_bullish_xover_days_ago=stochrsi_bullish_xover_days_ago,
                    stochrsi_bearish_xover_days_ago=stochrsi_bearish_xover_days_ago,
                    days_since_price_sma20_bull=days_since_price_sma20_bull,
                    days_since_price_sma50_bull=days_since_price_sma50_bull,
                    days_since_price_ema20_bull=days_since_price_ema20_bull,
                    days_since_ema9_ema20_bull=days_since_ema9_ema20_bull,
                    days_since_ema9_ema20_bear=days_since_ema9_ema20_bear,
                    days_since_sma20_sma50_bull=days_since_sma20_sma50_bull,
                    days_since_macd_bull=days_since_macd_bull,
                    days_since_macd_bear=days_since_macd_bear,
                    days_since_cmf_bull=days_since_cmf_bull,
                    days_since_cmf_bear=days_since_cmf_bear,
                    ema9_ema20_spread=ema9_ema20_spread,
                    macd_histogram_slope=macd_histogram_slope,
                    macd_above_zero=macd_above_zero,
                    cmf_slope_5d=cmf_slope_5d,
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
                snapshot.avg_traded_value = avg_traded_value
                snapshot.volume_breakout_ratio = volume_breakout_ratio
                snapshot.composite_score = composite_score
                snapshot.trend_score_val = trend_score_val
                snapshot.volume_score_val = volume_score_val
                snapshot.rs_score_val = rs_score_val
                snapshot.momentum_score_val = momentum_score_val
                snapshot.cmf_score_val = cmf_score_val
                snapshot.breakout_score_val = breakout_score_val
                snapshot.cmf_20 = cmf_20_snap
                snapshot.cmf_20_prev = cmf_20_prev_snap
                snapshot.cmf_crossed_above_zero = cmf_crossed_above_zero
                snapshot.stochrsi_k = stochrsi_k_snap
                snapshot.stochrsi_d = stochrsi_d_snap
                snapshot.stochrsi_zone = stochrsi_zone
                snapshot.stochrsi_bullish_xover_days_ago = stochrsi_bullish_xover_days_ago
                snapshot.stochrsi_bearish_xover_days_ago = stochrsi_bearish_xover_days_ago
                snapshot.days_since_price_sma20_bull = days_since_price_sma20_bull
                snapshot.days_since_price_sma50_bull = days_since_price_sma50_bull
                snapshot.days_since_price_ema20_bull = days_since_price_ema20_bull
                snapshot.days_since_ema9_ema20_bull  = days_since_ema9_ema20_bull
                snapshot.days_since_ema9_ema20_bear  = days_since_ema9_ema20_bear
                snapshot.days_since_sma20_sma50_bull = days_since_sma20_sma50_bull
                snapshot.days_since_macd_bull        = days_since_macd_bull
                snapshot.days_since_macd_bear        = days_since_macd_bear
                snapshot.days_since_cmf_bull         = days_since_cmf_bull
                snapshot.days_since_cmf_bear         = days_since_cmf_bear
                snapshot.ema9_ema20_spread           = ema9_ema20_spread
                snapshot.macd_histogram_slope        = macd_histogram_slope
                snapshot.macd_above_zero             = macd_above_zero
                snapshot.cmf_slope_5d                = cmf_slope_5d
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
        """Refreshes screening snapshots for all active symbols using bulk pre-fetching.

        Runs 7 bulk queries for the entire universe instead of ~9 queries per symbol,
        reducing total DB round-trips from ~6,300 to ~10 for a 700-stock universe.
        """
        import datetime as dt

        try:
            active_symbols = self.db.scalars(select(Symbol).filter_by(is_active=True)).all()
            if not active_symbols:
                return 0

            symbol_ids = [s.id for s in active_symbols]
            logger.info(f"Refreshing screening snapshots for {len(active_symbols)} active symbols...")

            nifty_21d_return = self._get_nifty_21d_return()
            if nifty_21d_return is not None:
                logger.debug(f"NIFTY 21D return for RS scoring: {nifty_21d_return:.4f}")

            mtf = self._mtf_thresholds()
            weekly_ema_len = mtf["weekly_ema"]

            # ── Bulk load 1: Prices — last 45 calendar days covers 21+ trading days
            #    and the 35-day RS window in a single query.
            price_cutoff = dt.date.today() - dt.timedelta(days=45)
            rs_cutoff    = dt.date.today() - dt.timedelta(days=35)
            raw_prices = []
            for chunk in self._id_chunks(symbol_ids):
                raw_prices.extend(
                    self.db.scalars(
                        select(DailyPrice)
                        .where(
                            DailyPrice.symbol_id.in_(chunk),
                            DailyPrice.trading_date >= price_cutoff,
                            DailyPrice.granularity == "1d",
                        )
                        .order_by(DailyPrice.symbol_id, DailyPrice.trading_date.desc())
                    ).all()
                )

            all_prices_by_symbol: dict[int, list] = defaultdict(list)
            for p in raw_prices:
                all_prices_by_symbol[p.symbol_id].append(p)

            prices_by_symbol   = {sid: rows[:21] for sid, rows in all_prices_by_symbol.items()}
            rs_oldest_by_symbol: dict[int, object] = {}
            for sid, price_list in all_prices_by_symbol.items():
                eligible = [p for p in price_list if p.trading_date >= rs_cutoff]
                if eligible:
                    rs_oldest_by_symbol[sid] = eligible[-1]  # oldest = last in desc-ordered list

            # ── Bulk load 2: Indicators — last 35 calendar days covers 22+ trading days
            ind_cutoff = dt.date.today() - dt.timedelta(days=35)
            raw_indicators = []
            for chunk in self._id_chunks(symbol_ids):
                raw_indicators.extend(
                    self.db.scalars(
                        select(DailyIndicator)
                        .where(
                            DailyIndicator.symbol_id.in_(chunk),
                            DailyIndicator.trading_date >= ind_cutoff,
                        )
                        .order_by(DailyIndicator.symbol_id, DailyIndicator.trading_date.desc())
                    ).all()
                )
            indicators_by_symbol: dict[int, list] = defaultdict(list)
            for ind in raw_indicators:
                indicators_by_symbol[ind.symbol_id].append(ind)
            indicators_by_symbol = {sid: rows[:22] for sid, rows in indicators_by_symbol.items()}

            # ── Bulk load 3: Latest Heikin-Ashi candle per symbol
            ha_by_symbol: dict = {}
            for chunk in self._id_chunks(symbol_ids):
                ha_subq = (
                    select(DailyHeikinAshi.symbol_id, func.max(DailyHeikinAshi.trading_date).label("max_date"))
                    .where(DailyHeikinAshi.symbol_id.in_(chunk))
                    .group_by(DailyHeikinAshi.symbol_id)
                    .subquery()
                )
                ha_by_symbol.update({
                    row.symbol_id: row
                    for row in self.db.scalars(
                        select(DailyHeikinAshi).join(
                            ha_subq,
                            (DailyHeikinAshi.symbol_id == ha_subq.c.symbol_id)
                            & (DailyHeikinAshi.trading_date == ha_subq.c.max_date),
                        )
                    ).all()
                })

            # ── Bulk load 4: Latest Renko brick per symbol
            brick_by_symbol: dict = {}
            for chunk in self._id_chunks(symbol_ids):
                renko_subq = (
                    select(RenkoBrick.symbol_id, func.max(RenkoBrick.brick_index).label("max_idx"))
                    .where(RenkoBrick.symbol_id.in_(chunk))
                    .group_by(RenkoBrick.symbol_id)
                    .subquery()
                )
                brick_by_symbol.update({
                    row.symbol_id: row
                    for row in self.db.scalars(
                        select(RenkoBrick).join(
                            renko_subq,
                            (RenkoBrick.symbol_id == renko_subq.c.symbol_id)
                            & (RenkoBrick.brick_index == renko_subq.c.max_idx),
                        )
                    ).all()
                })

            # ── Bulk load 5: Latest Line Break line per symbol
            lb_by_symbol: dict = {}
            for chunk in self._id_chunks(symbol_ids):
                lb_subq = (
                    select(LineBreakLine.symbol_id, func.max(LineBreakLine.line_index).label("max_idx"))
                    .where(LineBreakLine.symbol_id.in_(chunk))
                    .group_by(LineBreakLine.symbol_id)
                    .subquery()
                )
                lb_by_symbol.update({
                    row.symbol_id: row
                    for row in self.db.scalars(
                        select(LineBreakLine).join(
                            lb_subq,
                            (LineBreakLine.symbol_id == lb_subq.c.symbol_id)
                            & (LineBreakLine.line_index == lb_subq.c.max_idx),
                        )
                    ).all()
                })

            # ── Bulk load 6: Existing snapshots for upsert
            existing_snapshots: dict = {}
            for chunk in self._id_chunks(symbol_ids):
                existing_snapshots.update({
                    row.symbol_id: row
                    for row in self.db.scalars(
                        select(ScreeningSnapshot).where(ScreeningSnapshot.symbol_id.in_(chunk))
                    ).all()
                })

            # ── Bulk load 7: Weekly trend prices (~2.5 yrs of daily bars, resampled in Python)
            weekly_cutoff = dt.date.today() - dt.timedelta(weeks=max(weekly_ema_len * 2, 60) + 10)
            raw_weekly = []
            for chunk in self._id_chunks(symbol_ids):
                raw_weekly.extend(
                    self.db.execute(
                        select(DailyPrice.symbol_id, DailyPrice.trading_date, DailyPrice.close)
                        .where(
                            DailyPrice.symbol_id.in_(chunk),
                            DailyPrice.trading_date >= weekly_cutoff,
                            DailyPrice.granularity == "1d",
                        )
                        .order_by(DailyPrice.symbol_id, DailyPrice.trading_date.asc())
                    ).all()
                )
            weekly_rows_by_symbol: dict[int, list] = defaultdict(list)
            for row in raw_weekly:
                weekly_rows_by_symbol[row.symbol_id].append((row.trading_date, row.close))

            weekly_trend_by_symbol: dict[int, str | None] = {
                sid: self._compute_weekly_trend(sid, weekly_ema_len, rows=rows)
                for sid, rows in weekly_rows_by_symbol.items()
            }

            # ── Process each symbol using only pre-fetched data (no per-symbol DB queries)
            refreshed_count = 0
            for sym in active_symbols:
                try:
                    with self.db.begin_nested():
                        self.refresh_snapshot_for_symbol(
                            sym.id,
                            nifty_21d_return=nifty_21d_return,
                            commit=False,
                            _prefetch={
                                "symbol":       sym,
                                "prices":       prices_by_symbol.get(sym.id, []),
                                "rs_oldest":    rs_oldest_by_symbol.get(sym.id),
                                "ha":           ha_by_symbol.get(sym.id),
                                "ind_rows":     indicators_by_symbol.get(sym.id, []),
                                "brick":        brick_by_symbol.get(sym.id),
                                "lb":           lb_by_symbol.get(sym.id),
                                "snapshot":     existing_snapshots.get(sym.id),
                                "weekly_trend": weekly_trend_by_symbol.get(sym.id),
                            },
                        )
                    refreshed_count += 1
                except Exception as sym_err:
                    logger.error(f"Error refreshing snapshot for symbol {sym.symbol}: {sym_err}")

            self.db.commit()
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
        min_avg_traded_value: float | None = None,
        volume_breakout: str | None = None,
        only_nr7: bool = False,
        only_inside_bar: bool = False,
        only_gap_up: bool = False,
        only_gap_down: bool = False,
        min_rs_1m: float | None = None,
        # CMF filters
        min_cmf: float | None = None,
        max_cmf: float | None = None,
        cmf_rising: bool | None = None,
        cmf_crossed_zero: bool | None = None,
        # StochRSI filters
        max_stochrsi_k: float | None = None,
        min_stochrsi_k: float | None = None,
        stochrsi_bullish_xover_max_days: int | None = None,
        # Crossover recency filters
        ema_ribbon_bull_max_days: int | None = None,
        golden_cross_max_days: int | None = None,
        macd_bull_xover_max_days: int | None = None,
        cmf_bull_xover_max_days: int | None = None,
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
        # CMF filters
        if min_cmf is not None:
            stmt = stmt.where(ScreeningSnapshot.cmf_20 >= min_cmf)
        if max_cmf is not None:
            stmt = stmt.where(ScreeningSnapshot.cmf_20 <= max_cmf)
        if cmf_rising:
            stmt = stmt.where(
                ScreeningSnapshot.cmf_20 > ScreeningSnapshot.cmf_20_prev,
                ScreeningSnapshot.cmf_20.is_not(None),
                ScreeningSnapshot.cmf_20_prev.is_not(None),
            )
        if cmf_crossed_zero:
            stmt = stmt.where(ScreeningSnapshot.cmf_crossed_above_zero == True)  # noqa: E712
        # StochRSI filters
        if max_stochrsi_k is not None:
            stmt = stmt.where(ScreeningSnapshot.stochrsi_k <= max_stochrsi_k)
        if min_stochrsi_k is not None:
            stmt = stmt.where(ScreeningSnapshot.stochrsi_k >= min_stochrsi_k)
        if stochrsi_bullish_xover_max_days is not None:
            stmt = stmt.where(
                ScreeningSnapshot.stochrsi_bullish_xover_days_ago <= stochrsi_bullish_xover_max_days,
                ScreeningSnapshot.stochrsi_bullish_xover_days_ago.is_not(None),
            )
        if ema_ribbon_bull_max_days is not None:
            stmt = stmt.where(
                ScreeningSnapshot.days_since_ema9_ema20_bull <= ema_ribbon_bull_max_days,
                ScreeningSnapshot.days_since_ema9_ema20_bull.is_not(None),
            )
        if golden_cross_max_days is not None:
            stmt = stmt.where(
                ScreeningSnapshot.days_since_sma20_sma50_bull <= golden_cross_max_days,
                ScreeningSnapshot.days_since_sma20_sma50_bull.is_not(None),
            )
        if macd_bull_xover_max_days is not None:
            stmt = stmt.where(
                ScreeningSnapshot.days_since_macd_bull <= macd_bull_xover_max_days,
                ScreeningSnapshot.days_since_macd_bull.is_not(None),
            )
        if cmf_bull_xover_max_days is not None:
            stmt = stmt.where(
                ScreeningSnapshot.days_since_cmf_bull <= cmf_bull_xover_max_days,
                ScreeningSnapshot.days_since_cmf_bull.is_not(None),
            )

        stmt = stmt.order_by(ScreeningSnapshot.symbol.asc())

        # Optimize: if no volume filters are applied, we can apply SQL limit immediately
        has_volume_filters = min_avg_traded_value is not None or (
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
                DailyPrice.close,
                DailyPrice.volume,
                func.row_number()
                .over(partition_by=DailyPrice.symbol_id, order_by=DailyPrice.trading_date.desc())
                .label("rn"),
            )
            .where(DailyPrice.symbol_id.in_(symbol_ids_subq))
            .subquery()
        )

        stmt_prices = select(subq.c.symbol_id, subq.c.close, subq.c.volume).where(subq.c.rn <= 6)

        price_rows = self.db.execute(stmt_prices).all()

        # 2. Group by symbol_id
        from collections import defaultdict

        prices_by_symbol: dict[int, list[tuple[float, int]]] = defaultdict(list)
        for sym_id, close, vol in price_rows:
            prices_by_symbol[sym_id].append((float(close), int(vol)))

        # 3. Calculate avg traded value and breakout ratio, then apply memory filters
        filtered_results = []
        for snapshot in base_results:
            sym_id = snapshot.symbol_id
            sym_prices = prices_by_symbol.get(sym_id, [])

            latest_volume = sym_prices[0][1] if len(sym_prices) >= 1 else int(snapshot.volume)
            preceding = sym_prices[1:6] if len(sym_prices) > 1 else []

            if preceding:
                avg_traded_value = sum(c * v for c, v in preceding) / len(preceding)
                avg_vol = sum(v for _, v in preceding) / len(preceding)
            else:
                avg_traded_value = float(latest_volume) * float(snapshot.close_price or 0)
                avg_vol = float(latest_volume)

            breakout_ratio = (latest_volume / avg_vol) if avg_vol > 0 else 1.0

            # Attach dynamic calculated attributes
            snapshot.avg_traded_value = avg_traded_value
            snapshot.volume_breakout_ratio = breakout_ratio

            # Apply memory filtering criteria
            keep = True
            if min_avg_traded_value is not None:
                if avg_traded_value < min_avg_traded_value:
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
