import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
from loguru import logger
from stocks.config import Config

class MarketStructureEngine:
    """Engine to generate and maintain Heikin-Ashi candles, Renko bricks, and Line Break charts."""

    def __init__(self, config: Config):
        self.config = config

    def generate_heikin_ashi(
        self, df: pd.DataFrame, prev_candle: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Generates Heikin-Ashi candles from an OHLCV DataFrame.
        
        If a prev_candle is provided, it seeds the first candle's HA open/close using the previous values
        to enable highly efficient incremental recalculation.
        """
        if df.empty:
            return []

        df_sorted = df.sort_index()
        ha_candles = []
        
        # Seed variables
        if prev_candle:
            ha_open = float(prev_candle["open"])
            ha_close = float(prev_candle["close"])
        else:
            first_row = df_sorted.iloc[0]
            ha_open = (float(first_row["open"]) + float(first_row["close"])) / 2.0
            ha_close = (float(first_row["open"]) + float(first_row["high"]) + float(first_row["low"]) + float(first_row["close"])) / 4.0

        is_first = True
        for idx, row in df_sorted.iterrows():
            t_date = idx.date() if isinstance(idx, pd.Timestamp) else idx
            
            # If we are starting from a seeded candle, the very first row in df_sorted is the new row.
            # We calculate its Heikin-Ashi values sequentially
            o = float(row["open"])
            h = float(row["high"])
            l = float(row["low"])
            c = float(row["close"])
            
            if is_first and not prev_candle:
                curr_ha_open = ha_open
                curr_ha_close = ha_close
                curr_ha_high = max(h, curr_ha_open, curr_ha_close)
                curr_ha_low = min(l, curr_ha_open, curr_ha_close)
                is_first = False
            else:
                curr_ha_close = (o + h + l + c) / 4.0
                curr_ha_open = (ha_open + ha_close) / 2.0
                curr_ha_high = max(h, curr_ha_open, curr_ha_close)
                curr_ha_low = min(l, curr_ha_open, curr_ha_close)
            
            ha_candles.append({
                "trading_date": t_date,
                "open": curr_ha_open,
                "high": curr_ha_high,
                "low": curr_ha_low,
                "close": curr_ha_close
            })
            
            # Roll forward seeds
            ha_open = curr_ha_open
            ha_close = curr_ha_close
            is_first = False
            
        return ha_candles

    def generate_renko_bricks(
        self, df: pd.DataFrame, last_brick: Optional[Dict[str, Any]] = None, pct_brick_size: float = 0.01
    ) -> List[Dict[str, Any]]:
        """Generates path-dependent Renko bricks from a sorted EOD close price DataFrame.
        
        If last_brick is provided, it projects new bricks forward starting from the last_brick's index,
        end_date, and close price, bypassing full historical recalculations.
        """
        if df.empty:
            return []

        df_sorted = df.sort_index()
        new_bricks = []
        
        if last_brick:
            brick_idx = int(last_brick["brick_index"])
            prev_close = float(last_brick["close"])
            brick_size = float(last_brick["brick_size"])
            # Load only prices strictly after the last brick's end_date
            last_date = last_brick["end_date"]
            prices_to_process = df_sorted[df_sorted.index.date > last_date] if isinstance(df_sorted.index, pd.DatetimeIndex) else df_sorted
        else:
            brick_idx = 0
            first_close = float(df_sorted.iloc[0]["close"])
            prev_close = first_close
            brick_size = first_close * pct_brick_size  # Default to 1% of the starting price
            prices_to_process = df_sorted

        for idx, row in prices_to_process.iterrows():
            t_date = idx.date() if isinstance(idx, pd.Timestamp) else idx
            c_price = float(row["close"])
            
            price_diff = c_price - prev_close
            
            # We can form multiple bricks in a single high-volatility day
            while abs(price_diff) >= brick_size:
                brick_idx += 1
                start_date = t_date  # Simple projection: set start/end date to current row's date
                
                if price_diff >= brick_size:
                    # UP Brick
                    brick = {
                        "brick_index": brick_idx,
                        "start_date": start_date,
                        "end_date": t_date,
                        "open": prev_close,
                        "close": prev_close + brick_size,
                        "direction": "UP",
                        "brick_size": brick_size
                    }
                    prev_close = prev_close + brick_size
                else:
                    # DOWN Brick
                    brick = {
                        "brick_index": brick_idx,
                        "start_date": start_date,
                        "end_date": t_date,
                        "open": prev_close,
                        "close": prev_close - brick_size,
                        "direction": "DOWN",
                        "brick_size": brick_size
                    }
                    prev_close = prev_close - brick_size
                    
                new_bricks.append(brick)
                price_diff = c_price - prev_close
                
        return new_bricks

    def generate_line_breaks(
        self, df: pd.DataFrame, last_lines: List[Dict[str, Any]] = None, break_count: int = 3
    ) -> List[Dict[str, Any]]:
        """Generates path-dependent Line Break chart lines from a sorted EOD close DataFrame.
        
        If last_lines (N previous lines) is provided, it projects new lines forward starting from the
        last line's index and end_date, validating reversals against the N-line boundaries.
        """
        if df.empty:
            return []

        df_sorted = df.sort_index()
        new_lines = []
        
        if last_lines:
            # We need the last N lines to evaluate reversals
            active_lines = list(last_lines)
            line_idx = int(active_lines[-1]["line_index"])
            prev_line = active_lines[-1]
            last_date = prev_line["end_date"]
            prices_to_process = df_sorted[df_sorted.index.date > last_date] if isinstance(df_sorted.index, pd.DatetimeIndex) else df_sorted
        else:
            if len(df_sorted) < 2:
                return []
            
            active_lines = []
            line_idx = 1
            close_0 = float(df_sorted.iloc[0]["close"])
            close_1 = float(df_sorted.iloc[1]["close"])
            
            # Build the first line
            dir_str = "UP" if close_1 > close_0 else "DOWN"
            first_line = {
                "line_index": line_idx,
                "start_date": df_sorted.index[0].date() if isinstance(df_sorted.index, pd.DatetimeIndex) else df_sorted.index[0],
                "end_date": df_sorted.index[1].date() if isinstance(df_sorted.index, pd.DatetimeIndex) else df_sorted.index[1],
                "open": close_0,
                "close": close_1,
                "direction": dir_str
            }
            active_lines.append(first_line)
            new_lines.append(first_line)
            prices_to_process = df_sorted.iloc[2:]
            
        for idx, row in prices_to_process.iterrows():
            t_date = idx.date() if isinstance(idx, pd.Timestamp) else idx
            c_price = float(row["close"])
            
            prev_line = active_lines[-1]
            p_open = float(prev_line["open"])
            p_close = float(prev_line["close"])
            p_dir = prev_line["direction"]
            
            line_added = False
            
            if p_dir == "UP":
                if c_price > p_close:
                    # Continues UP
                    line_idx += 1
                    new_line = {
                        "line_index": line_idx,
                        "start_date": t_date,
                        "end_date": t_date,
                        "open": p_close,
                        "close": c_price,
                        "direction": "UP"
                    }
                    active_lines.append(new_line)
                    new_lines.append(new_line)
                    line_added = True
                else:
                    # Check for DOWN Reversal: Close must break the lowest low of the last N active lines
                    last_n = active_lines[-break_count:]
                    lowest_low = min(min(float(l["open"]), float(l["close"])) for l in last_n)
                    if c_price < lowest_low:
                        line_idx += 1
                        new_line = {
                            "line_index": line_idx,
                            "start_date": t_date,
                            "end_date": t_date,
                            "open": p_close,
                            "close": c_price,
                            "direction": "DOWN"
                        }
                        active_lines.append(new_line)
                        new_lines.append(new_line)
                        line_added = True
            else:  # prev_line is DOWN
                if c_price < p_close:
                    # Continues DOWN
                    line_idx += 1
                    new_line = {
                        "line_index": line_idx,
                        "start_date": t_date,
                        "end_date": t_date,
                        "open": p_close,
                        "close": c_price,
                        "direction": "DOWN"
                    }
                    active_lines.append(new_line)
                    new_lines.append(new_line)
                    line_added = True
                else:
                    # Check for UP Reversal: Close must break the highest high of the last N active lines
                    last_n = active_lines[-break_count:]
                    highest_high = max(max(float(l["open"]), float(l["close"])) for l in last_n)
                    if c_price > highest_high:
                        line_idx += 1
                        new_line = {
                            "line_index": line_idx,
                            "start_date": t_date,
                            "end_date": t_date,
                            "open": p_close,
                            "close": c_price,
                            "direction": "UP"
                        }
                        active_lines.append(new_line)
                        new_lines.append(new_line)
                        line_added = True
                        
            # Keep active_lines pruned to prevent memory memory leaks during long runs
            if line_added and len(active_lines) > break_count:
                active_lines = active_lines[-break_count:]
                
        return new_lines
