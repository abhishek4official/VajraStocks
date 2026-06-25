import datetime

import numpy as np
import pandas as pd

from stocks.services.indicator_engine import IndicatorEngine


def test_technical_indicator_calculations(test_config):
    """Verifies that the IndicatorEngine calculates all defined indicators correctly."""
    engine = IndicatorEngine(test_config)

    # Generate 250 dummy trading days
    dates = [datetime.date(2026, 1, 1) + datetime.timedelta(days=i) for i in range(250)]

    # Create price values: a steady upwards trend to calculate crossovers
    prices = np.linspace(100.0, 200.0, 250)

    data = {"open": prices - 1.0, "high": prices + 2.0, "low": prices - 2.0, "close": prices, "volume": [10000] * 250}

    df = pd.DataFrame(data, index=pd.to_datetime(dates))

    # Calculate indicators
    df_calc = engine.calculate_indicators(df)

    # Verify all expected column bindings exist
    expected_cols = [
        "rsi_14",
        "atr_14",
        "sma_20",
        "sma_50",
        "sma_200",
        "ema_9",
        "ema_21",
        "macd_line",
        "macd_histogram",
        "macd_signal",
        "bb_lower",
        "bb_middle",
        "bb_upper",
    ]
    for col in expected_cols:
        assert col in df_calc.columns, f"Indicator column {col} was not appended."

    # Check simple values (e.g. SMA 200 needs 200 rows, so it should be null for first 199 rows and valid for 200th row)
    assert pd.isna(df_calc["sma_200"].iloc[0])
    assert pd.isna(df_calc["sma_200"].iloc[198])
    assert not pd.isna(df_calc["sma_200"].iloc[199])

    # Verify SMA 200 value is correct (since it is a linear linspace, the average of first 200 elements is correct)
    expected_sma_200 = df["close"].iloc[0:200].mean()
    assert np.isclose(df_calc["sma_200"].iloc[199], expected_sma_200)

    # Verify Bollinger Bands (middle is just SMA 20)
    assert np.isclose(df_calc["bb_middle"].iloc[19], df_calc["sma_20"].iloc[19])
