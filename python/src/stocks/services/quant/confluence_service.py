# src/stocks/services/quant/confluence_service.py
import datetime
import json
from collections import defaultdict
from typing import Any
from loguru import logger
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from stocks.db.models import DailyPrice, DailyIndicator, SymbolConfluenceLevel, Symbol


class ConfluenceService:
    """Calculates high-probability structural Support & Resistance zones using Confluence Scoring."""

    def __init__(self, db_session: Session):
        self.db = db_session

    def calculate_and_save_levels(self, symbol_id: int) -> list[SymbolConfluenceLevel]:
        """Calculates confluence S/R levels for a symbol and stores them in the database."""
        # 1. Fetch historical price data (last 200 daily bars to cover swing lookbacks and volume profile)
        prices = self.db.scalars(
            select(DailyPrice)
            .filter_by(symbol_id=symbol_id, granularity="1d")
            .order_by(DailyPrice.trading_date.desc())
            .limit(200)
        ).all()

        if not prices:
            logger.warning(f"No price history found for symbol_id {symbol_id}. Cannot compute confluence levels.")
            return []

        # Latest close price to distinguish support vs resistance
        latest_price = float(prices[0].close)

        # 2. Fetch latest ATR and EMAs
        latest_indicator = self.db.scalar(
            select(DailyIndicator)
            .filter_by(symbol_id=symbol_id, granularity="1d")
            .order_by(DailyIndicator.trading_date.desc())
            .limit(1)
        )

        atr = float(latest_indicator.atr_14) if latest_indicator and latest_indicator.atr_14 else latest_price * 0.02
        sma_50 = float(latest_indicator.sma_50) if latest_indicator and latest_indicator.sma_50 is not None else None
        sma_200 = float(latest_indicator.sma_200) if latest_indicator and latest_indicator.sma_200 is not None else None

        # 3. Gather raw levels and their weights
        raw_levels = []

        # A. Swing Highs / Swing Lows (Weight: 30)
        # Lookback window of 5 days: check if a candle's high/low is higher/lower than 5 days before and after
        # Since prices list is sorted by date DESC, index 0 is latest.
        # We need chronological order to check neighbors properly.
        chrono_prices = list(reversed(prices))
        window = 5
        for i in range(window, len(chrono_prices) - window):
            slice_window = chrono_prices[i - window : i + window + 1]
            highs = [float(p.high) for p in slice_window]
            lows = [float(p.low) for p in slice_window]
            
            curr_high = float(chrono_prices[i].high)
            curr_low = float(chrono_prices[i].low)

            if curr_high == max(highs):
                raw_levels.append({
                    "price": curr_high,
                    "score": 30,
                    "component": "SWING",
                    "type": "RESISTANCE" if curr_high > latest_price else "SUPPORT"
                })
            if curr_low == min(lows):
                raw_levels.append({
                    "price": curr_low,
                    "score": 30,
                    "component": "SWING",
                    "type": "SUPPORT" if curr_low < latest_price else "RESISTANCE"
                })

        # B. High Volume Nodes / Volume Profile (Weight: 25)
        # Create a volume profile using 10 price bins over the last 100 days
        profile_len = min(100, len(prices))
        recent_prices = prices[:profile_len]
        lows_recent = [float(p.low) for p in recent_prices]
        highs_recent = [float(p.high) for p in recent_prices]
        
        if lows_recent and highs_recent:
            min_p, max_p = min(lows_recent), max(highs_recent)
            price_range = max_p - min_p
            if price_range > 0:
                bin_count = 10
                bin_width = price_range / bin_count
                bins_vol = [0.0] * bin_count
                
                # Distribute candle volume into the bins it overlaps
                for p in recent_prices:
                    c_low, c_high = float(p.low), float(p.high)
                    c_vol = float(p.volume)
                    # Find which bins this candle falls into
                    for b_idx in range(bin_count):
                        b_low = min_p + b_idx * bin_width
                        b_high = b_low + bin_width
                        # If candle overlaps this bin, add a fraction of its volume
                        overlap_low = max(c_low, b_low)
                        overlap_high = min(c_high, b_high)
                        if overlap_high > overlap_low:
                            overlap_pct = (overlap_high - overlap_low) / (c_high - c_low) if (c_high - c_low) > 0 else 1.0
                            bins_vol[b_idx] += c_vol * overlap_pct

                # Find bins with above-average volume
                avg_vol = sum(bins_vol) / bin_count
                for b_idx, vol in enumerate(bins_vol):
                    if vol > avg_vol:
                        bin_mid = min_p + (b_idx + 0.5) * bin_width
                        raw_levels.append({
                            "price": bin_mid,
                            "score": 25,
                            "component": "HVN",
                            "type": "SUPPORT" if bin_mid < latest_price else "RESISTANCE"
                        })

        # C. Quant Pivot Levels (Weight: 20)
        # We calculate the Weekly and Monthly Pivot Points based on the previous period
        # Let's group daily prices by calendar week and calendar month
        weekly_groups = defaultdict(list)
        monthly_groups = defaultdict(list)
        
        for p in prices:
            dt = p.trading_date
            year, week, _ = dt.isocalendar()
            weekly_groups[(year, week)].append(p)
            monthly_groups[(dt.year, dt.month)].append(p)

        # Sort the periods to easily retrieve the previous one
        sorted_weeks = sorted(weekly_groups.keys(), reverse=True)
        sorted_months = sorted(monthly_groups.keys(), reverse=True)

        def get_ohlc(period_prices):
            h = max(float(p.high) for p in period_prices)
            l = min(float(p.low) for p in period_prices)
            c = float(period_prices[0].close) # close of latest day in period
            return h, l, c

        # Weekly Pivot
        if len(sorted_weeks) > 1:
            prev_week_prices = weekly_groups[sorted_weeks[1]]
            wh, wl, wc = get_ohlc(prev_week_prices)
            wpp = (wh + wl + wc) / 3.0
            ws1 = 2 * wpp - wh
            wr1 = 2 * wpp - wl
            ws2 = wpp - (wh - wl)
            wr2 = wpp + (wh - wl)
            for price, name in [(ws1, "WS1"), (ws2, "WS2"), (wr1, "WR1"), (wr2, "WR2"), (wpp, "WPP")]:
                raw_levels.append({
                    "price": price,
                    "score": 20,
                    "component": "PIVOT",
                    "type": "SUPPORT" if price < latest_price else "RESISTANCE"
                })

        # Monthly Pivot
        if len(sorted_months) > 1:
            prev_month_prices = monthly_groups[sorted_months[1]]
            mh, ml, mc = get_ohlc(prev_month_prices)
            mpp = (mh + ml + mc) / 3.0
            ms1 = 2 * mpp - mh
            mr1 = 2 * mpp - ml
            ms2 = mpp - (mh - ml)
            mr2 = mpp + (mh - ml)
            for price, name in [(ms1, "MS1"), (ms2, "MS2"), (mr1, "MR1"), (mr2, "MR2"), (mpp, "MPP")]:
                raw_levels.append({
                    "price": price,
                    "score": 20,
                    "component": "PIVOT",
                    "type": "SUPPORT" if price < latest_price else "RESISTANCE"
                })

        # D. Moving Average Confluence (Weight: 15)
        if sma_50:
            raw_levels.append({
                "price": sma_50,
                "score": 15,
                "component": "EMA50",
                "type": "SUPPORT" if sma_50 < latest_price else "RESISTANCE"
            })
        if sma_200:
            raw_levels.append({
                "price": sma_200,
                "score": 15,
                "component": "EMA200",
                "type": "SUPPORT" if sma_200 < latest_price else "RESISTANCE"
            })

        # 4. Clustering Algorithm using 0.5 * ATR
        cluster_threshold = max(0.5 * atr, latest_price * 0.005) # at least 0.5% of price
        
        # Sort levels by price to cluster sequentially
        sorted_levels = sorted(raw_levels, key=lambda x: x["price"])
        
        clusters = []
        for lvl in sorted_levels:
            # Try to place in an existing cluster that is close
            placed = False
            for cluster in clusters:
                avg_price = sum(x["price"] for x in cluster) / len(cluster)
                if abs(lvl["price"] - avg_price) <= cluster_threshold:
                    cluster.append(lvl)
                    placed = True
                    break
            if not placed:
                clusters.append([lvl])

        # 5. Summarize and score each cluster
        final_levels = []
        for cluster in clusters:
            # Combined price is the weighted average or simple average.
            # Let's use simple average of the component prices.
            prices_in_cluster = [x["price"] for x in cluster]
            cluster_price = sum(prices_in_cluster) / len(cluster)

            # Sum the unique component scores (e.g. if we have multiple pivots in one cluster, count it once or count unique component names)
            score = 0
            component_names = set()
            for x in cluster:
                # Add to components set
                component_names.add(x["component"])

            # Calculate score as the sum of unique components in the cluster
            components_score_map = {
                "SWING": 30,
                "HVN": 25,
                "PIVOT": 20,
                "EMA50": 15,
                "EMA200": 15
            }
            for comp in component_names:
                score += components_score_map.get(comp, 10)

            # Cap total score at 100
            score = min(100, score)

            # Classify support vs resistance based on current price
            level_type = "SUPPORT" if cluster_price < latest_price else "RESISTANCE"
            
            final_levels.append({
                "price": round(cluster_price, 2),
                "strength_score": score,
                "level_type": level_type,
                "components": ",".join(sorted(list(component_names)))
            })

        # Separate Support and Resistance
        supports = [x for x in final_levels if x["level_type"] == "SUPPORT"]
        resistances = [x for x in final_levels if x["level_type"] == "RESISTANCE"]

        # Sort supports DESC (closest to price first) and select top 3
        supports = sorted(supports, key=lambda x: x["price"], reverse=True)[:3]
        # Sort resistances ASC (closest to price first) and select top 3
        resistances = sorted(resistances, key=lambda x: x["price"])[:3]

        # 6. Database persistence: Delete existing levels for this symbol and insert the new ones
        self.db.execute(delete(SymbolConfluenceLevel).filter_by(symbol_id=symbol_id))
        
        saved_entities = []
        for lvl in (supports + resistances):
            entity = SymbolConfluenceLevel(
                symbol_id=symbol_id,
                level_type=lvl["level_type"],
                price=lvl["price"],
                strength_score=lvl["strength_score"],
                components=lvl["components"]
            )
            self.db.add(entity)
            saved_entities.append(entity)

        self.db.commit()
        logger.info(f"Calculated and saved {len(saved_entities)} confluence levels for symbol_id {symbol_id}.")
        return saved_entities
