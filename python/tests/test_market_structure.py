import datetime

import numpy as np
import pandas as pd

from stocks.services.market_structure import MarketStructureEngine


def test_heikin_ashi_calculation(test_config):
    """Verifies that the MarketStructureEngine calculates Heikin-Ashi candles correctly."""
    engine = MarketStructureEngine(test_config)

    dates = [datetime.date(2026, 1, 1) + datetime.timedelta(days=i) for i in range(5)]
    data = {
        "open": [100.0, 102.0, 101.0, 105.0, 107.0],
        "high": [105.0, 106.0, 104.0, 109.0, 110.0],
        "low": [98.0, 101.0, 99.0, 104.0, 106.0],
        "close": [102.0, 103.0, 102.0, 108.0, 108.0],
        "volume": [1000] * 5,
    }
    df = pd.DataFrame(data, index=pd.to_datetime(dates))

    # 1. Test calculation without seed
    ha_candles = engine.generate_heikin_ashi(df)
    assert len(ha_candles) == 5

    # Verify first candle close = (O + H + L + C) / 4.0
    first_ha = ha_candles[0]
    expected_c0 = (100.0 + 105.0 + 98.0 + 102.0) / 4.0
    expected_o0 = (100.0 + 102.0) / 2.0
    assert np.isclose(first_ha["close"], expected_c0)
    assert np.isclose(first_ha["open"], expected_o0)

    # Verify second candle
    second_ha = ha_candles[1]
    expected_o1 = (expected_o0 + expected_c0) / 2.0
    assert np.isclose(second_ha["open"], expected_o1)

    # 2. Test incremental calculation with a seed candle
    seed_candle = {
        "trading_date": datetime.date(2025, 12, 31),
        "open": 98.0,
        "high": 102.0,
        "low": 97.0,
        "close": 100.0,
    }
    # Calculate for the remaining days using the seed
    ha_candles_seeded = engine.generate_heikin_ashi(df, prev_candle=seed_candle)
    assert len(ha_candles_seeded) == 5

    # First candle in seeded run should use seed's open/close for its open value
    first_seeded = ha_candles_seeded[0]
    expected_seeded_o0 = (seed_candle["open"] + seed_candle["close"]) / 2.0
    assert np.isclose(first_seeded["open"], expected_seeded_o0)


def test_renko_brick_calculation(test_config):
    """Verifies that the MarketStructureEngine generates Renko bricks properly."""
    engine = MarketStructureEngine(test_config)

    dates = [datetime.date(2026, 1, 1) + datetime.timedelta(days=i) for i in range(6)]
    data = {"close": [100.0, 102.0, 105.0, 103.0, 98.0, 97.0]}
    df = pd.DataFrame(data, index=pd.to_datetime(dates))

    # 1. Without last_brick (using pct_brick_size = 0.02, which is 2.0 starting brick size from close 100.0)
    bricks = engine.generate_renko_bricks(df, pct_brick_size=0.02)

    # Starting price is 100.0, brick size is 2.0.
    # Close 100 -> 102 (UP brick 1, open 100, close 102)
    # Close 102 -> 105 (price diff from 102 is 3.0, which >= 2.0. So UP brick 2, open 102, close 104)
    # Close 105 -> 103 (diff from 104 is -1.0, not >= 2.0. No bricks.)
    # Close 103 -> 98 (diff from 104 is -6.0. This is >= 3 bricks down!
    #   - Brick 3: DOWN open 104, close 102
    #   - Brick 4: DOWN open 102, close 100
    #   - Brick 5: DOWN open 100, close 98)
    # Close 98 -> 97 (diff from 98 is -1.0, no brick.)
    assert len(bricks) == 5
    assert bricks[0]["direction"] == "UP"
    assert bricks[0]["open"] == 100.0
    assert bricks[0]["close"] == 102.0
    assert bricks[0]["brick_index"] == 1

    assert bricks[1]["direction"] == "UP"
    assert bricks[1]["open"] == 102.0
    assert bricks[1]["close"] == 104.0
    assert bricks[1]["brick_index"] == 2

    assert bricks[2]["direction"] == "DOWN"
    assert bricks[2]["open"] == 104.0
    assert bricks[2]["close"] == 102.0
    assert bricks[2]["brick_index"] == 3

    # 2. Test incremental calculation with last_brick
    last_brick = bricks[1]  # Brick index 2, close 104, end_date = 2026-01-03

    # We pass the full dataframe. It should process prices strictly AFTER last_brick["end_date"] (which is 2026-01-03)
    # The prices after are 2026-01-04 (103.0), 2026-01-05 (98.0), 2026-01-06 (97.0).
    new_bricks = engine.generate_renko_bricks(df, last_brick=last_brick)

    # The new bricks should correspond to Brick 3, 4, 5.
    assert len(new_bricks) == 3
    new_brick_indices = [b["brick_index"] for b in new_bricks]
    assert new_brick_indices == [3, 4, 5]
    assert new_bricks[0]["open"] == 104.0
    assert new_bricks[0]["close"] == 102.0


def test_line_break_calculation(test_config):
    """Verifies that the MarketStructureEngine generates N-Line Break lines correctly."""
    engine = MarketStructureEngine(test_config)

    # We want to test 3-Line Break reversals.
    dates = [datetime.date(2026, 1, 1) + datetime.timedelta(days=i) for i in range(8)]
    # A sequence designed to trigger a 3-line break reversal.
    # Line 1: 100 -> 105 (UP)
    # Line 2: 105 -> 110 (UP)
    # Line 3: 110 -> 115 (UP)
    # Day 5: 112 (doesn't break the low of 3 lines, which is 100)
    # Day 6: 98 (breaks the lowest low of the last 3 lines, which is 100. DOWN Reversal!)
    data = {"close": [100.0, 105.0, 110.0, 115.0, 112.0, 98.0, 97.0, 102.0]}
    df = pd.DataFrame(data, index=pd.to_datetime(dates))

    # 1. Full generation without active previous lines
    lines = engine.generate_line_breaks(df, break_count=3)

    # Let's trace it:
    # 100 -> 105: Line 1 (UP)
    # 105 -> 110: Line 2 (UP)
    # 110 -> 115: Line 3 (UP)
    # 112: no line (not higher than 115, not lower than lowest low of last 3 lines [100.0])
    # 98: Line 4 (DOWN Reversal, open 115, close 98)
    # 97: Line 5 (DOWN Continuation, open 98, close 97)
    # 102: Line 6 (UP Reversal? Let's check last 3 lines:
    #      Line 3: UP open 110, close 115
    #      Line 4: DOWN open 115, close 98
    #      Line 5: DOWN open 98, close 97
    #      The highest high of the last 3 lines (Lines 3, 4, 5) is 115. Close 102 does NOT break 115.
    #      Wait, is the highest high of last 3 lines 115? Yes. So 102 does not trigger reversal.
    assert len(lines) == 5

    assert lines[0]["direction"] == "UP"
    assert lines[0]["open"] == 100.0
    assert lines[0]["close"] == 105.0

    assert lines[1]["direction"] == "UP"
    assert lines[2]["direction"] == "UP"

    assert lines[3]["direction"] == "DOWN"
    assert lines[3]["open"] == 115.0
    assert lines[3]["close"] == 98.0

    assert lines[4]["direction"] == "DOWN"
    assert lines[4]["open"] == 98.0
    assert lines[4]["close"] == 97.0

    # 2. Test incremental calculation with last_lines seed
    # We pass the last 3 lines as seed: Line 2, Line 3, Line 4 (or just Line 3, Line 4, Line 5)
    seed_lines = lines[2:5]  # Index 2, 3, 4 (Lines 3, 4, 5)

    # We process starting after the end date of Line 5 (which is 2026-01-07, day index 6)
    # Next date is 2026-01-08 (102.0)
    new_lines = engine.generate_line_breaks(df, last_lines=seed_lines, break_count=3)

    # 102.0 should not produce a new line because it doesn't break 115.
    assert len(new_lines) == 0
