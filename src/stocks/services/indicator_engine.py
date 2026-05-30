import pandas as pd
import pandas_ta as ta
from loguru import logger
from stocks.config import Config

class IndicatorEngine:
    """Engine using pandas-ta to compute vectorized technical indicators on historical OHLCV dataframes."""

    def __init__(self, config: Config):
        self.config = config

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculates standard technical indicators and appends them to the input DataFrame.
        
        Assumes input has columns: 'open', 'high', 'low', 'close', 'volume' and is indexed by date.
        """
        if df.empty:
            return df
            
        # Sort chronologically to ensure accurate rolling calculations
        df_sorted = df.sort_index()
        
        try:
            # 1. RSI (14)
            df_sorted["rsi_14"] = ta.rsi(df_sorted["close"], length=14)
            
            # 2. ATR (14)
            df_sorted["atr_14"] = ta.atr(df_sorted["high"], df_sorted["low"], df_sorted["close"], length=14)
            
            # 3. SMAs (20, 50, 200)
            df_sorted["sma_20"] = ta.sma(df_sorted["close"], length=20)
            df_sorted["sma_50"] = ta.sma(df_sorted["close"], length=50)
            df_sorted["sma_200"] = ta.sma(df_sorted["close"], length=200)
            
            # 4. EMAs (9, 21)
            df_sorted["ema_9"] = ta.ema(df_sorted["close"], length=9)
            df_sorted["ema_21"] = ta.ema(df_sorted["close"], length=21)
            
            # 5. MACD (12, 26, 9)
            macd_df = ta.macd(df_sorted["close"], fast=12, slow=26, signal=9)
            if macd_df is not None and not macd_df.empty:
                df_sorted["macd_line"] = macd_df.iloc[:, 0]
                df_sorted["macd_histogram"] = macd_df.iloc[:, 1]
                df_sorted["macd_signal"] = macd_df.iloc[:, 2]
            else:
                df_sorted["macd_line"] = None
                df_sorted["macd_histogram"] = None
                df_sorted["macd_signal"] = None
                
            # 6. Bollinger Bands (20, 2)
            bb_df = ta.bbands(df_sorted["close"], length=20, std=2)
            if bb_df is not None and not bb_df.empty:
                df_sorted["bb_lower"] = bb_df.iloc[:, 0]
                df_sorted["bb_middle"] = bb_df.iloc[:, 1]
                df_sorted["bb_upper"] = bb_df.iloc[:, 2]
            else:
                df_sorted["bb_lower"] = None
                df_sorted["bb_middle"] = None
                df_sorted["bb_upper"] = None
                
        except Exception as e:
            logger.error(f"Error calculating technical indicators via pandas-ta: {e}")
            raise e
            
        return df_sorted
