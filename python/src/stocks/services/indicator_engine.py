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

            # 4. EMAs (9, 20, 21)
            df_sorted["ema_9"]  = ta.ema(df_sorted["close"], length=9)
            df_sorted["ema_20"] = ta.ema(df_sorted["close"], length=20)
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

            # 7. ADX(14) + Directional Indicators
            adx_df = ta.adx(df_sorted["high"], df_sorted["low"], df_sorted["close"], length=14)
            if adx_df is not None and not adx_df.empty:
                df_sorted["adx_14"]   = adx_df.get("ADX_14",  adx_df.iloc[:, 0])
                df_sorted["plus_di"]  = adx_df.get("DMP_14",  adx_df.iloc[:, 1])
                df_sorted["minus_di"] = adx_df.get("DMN_14",  adx_df.iloc[:, 2])
            else:
                df_sorted["adx_14"] = None
                df_sorted["plus_di"] = None
                df_sorted["minus_di"] = None

            # 8. OBV
            obv_s = ta.obv(df_sorted["close"], df_sorted["volume"])
            df_sorted["obv"] = obv_s if obv_s is not None else None

            # 9. Supertrend(10, 3)
            st_df = ta.supertrend(df_sorted["high"], df_sorted["low"], df_sorted["close"], length=10, multiplier=3)
            if st_df is not None and not st_df.empty:
                dir_col = next((c for c in st_df.columns if c.startswith("SUPERTd")), None)
                val_col = next((c for c in st_df.columns if c.startswith("SUPERT_")), None)
                if val_col:
                    df_sorted["supertrend"] = st_df[val_col]
                else:
                    df_sorted["supertrend"] = None
                if dir_col:
                    # pandas-ta returns 1 (bullish) or -1 (bearish)
                    df_sorted["supertrend_dir"] = st_df[dir_col].map(lambda x: "UP" if x == 1 else ("DOWN" if x == -1 else None))
                else:
                    df_sorted["supertrend_dir"] = None
            else:
                df_sorted["supertrend"] = None
                df_sorted["supertrend_dir"] = None

            # 10. Stochastic(14, 3, 3)
            stoch_df = ta.stoch(df_sorted["high"], df_sorted["low"], df_sorted["close"], k=14, d=3, smooth_k=3)
            if stoch_df is not None and not stoch_df.empty:
                k_col = next((c for c in stoch_df.columns if c.startswith("STOCHk")), None)
                d_col = next((c for c in stoch_df.columns if c.startswith("STOCHd")), None)
                df_sorted["stoch_k"] = stoch_df[k_col] if k_col else None
                df_sorted["stoch_d"] = stoch_df[d_col] if d_col else None
            else:
                df_sorted["stoch_k"] = None
                df_sorted["stoch_d"] = None

            # 11. Chaikin Money Flow (20) — requires High, Low, Close, Volume
            cmf_s = ta.cmf(df_sorted["high"], df_sorted["low"], df_sorted["close"], df_sorted["volume"], length=20)
            df_sorted["cmf_20"] = cmf_s if cmf_s is not None else None

            # 12. Stochastic RSI (14, 14, 3, 3)
            srsi_df = ta.stochrsi(df_sorted["close"], length=14, rsi_length=14, k=3, d=3)
            if srsi_df is not None and not srsi_df.empty:
                k_col = next((c for c in srsi_df.columns if "STOCHRSIk" in c), None)
                d_col = next((c for c in srsi_df.columns if "STOCHRSId" in c), None)
                df_sorted["stochrsi_k"] = srsi_df[k_col] if k_col else None
                df_sorted["stochrsi_d"] = srsi_df[d_col] if d_col else None
            else:
                df_sorted["stochrsi_k"] = None
                df_sorted["stochrsi_d"] = None

            # 13. StochRSI crossover flags — vectorized shift comparison
            if "stochrsi_k" in df_sorted.columns and "stochrsi_d" in df_sorted.columns:
                k = df_sorted["stochrsi_k"]
                d = df_sorted["stochrsi_d"]
                k_prev = k.shift(1)
                d_prev = d.shift(1)
                df_sorted["stochrsi_bullish_xover"] = (k > d) & (k_prev <= d_prev)
                df_sorted["stochrsi_bearish_xover"] = (k < d) & (k_prev >= d_prev)
            else:
                df_sorted["stochrsi_bullish_xover"] = None
                df_sorted["stochrsi_bearish_xover"] = None

        except Exception as e:
            logger.error(f"Error calculating technical indicators via pandas-ta: {e}")
            raise e

        return df_sorted
