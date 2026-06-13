import datetime
from typing import Optional

from sqlalchemy import (
    BIGINT,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""

    pass


class Symbol(Base):
    """Model representing an NSE Equity Symbol."""

    __tablename__ = "symbols"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    isin: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    series: Mapped[str] = mapped_column(String(10), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    prices: Mapped[list["DailyPrice"]] = relationship(
        "DailyPrice", back_populates="symbol_obj", cascade="all, delete-orphan"
    )
    actions: Mapped[list["CorporateAction"]] = relationship(
        "CorporateAction", back_populates="symbol_obj", cascade="all, delete-orphan"
    )
    sync_state: Mapped[Optional["SymbolSyncState"]] = relationship(
        "SymbolSyncState", back_populates="symbol_obj", uselist=False, cascade="all, delete-orphan"
    )
    indicators: Mapped[list["DailyIndicator"]] = relationship(
        "DailyIndicator", back_populates="symbol_obj", cascade="all, delete-orphan"
    )
    heikin_ashi: Mapped[list["DailyHeikinAshi"]] = relationship(
        "DailyHeikinAshi", back_populates="symbol_obj", cascade="all, delete-orphan"
    )
    renko_bricks: Mapped[list["RenkoBrick"]] = relationship(
        "RenkoBrick", back_populates="symbol_obj", cascade="all, delete-orphan"
    )
    line_break_lines: Mapped[list["LineBreakLine"]] = relationship(
        "LineBreakLine", back_populates="symbol_obj", cascade="all, delete-orphan"
    )
    screening_snapshot: Mapped[Optional["ScreeningSnapshot"]] = relationship(
        "ScreeningSnapshot", back_populates="symbol_obj", uselist=False, cascade="all, delete-orphan"
    )
    confluence_levels: Mapped[list["SymbolConfluenceLevel"]] = relationship(
        "SymbolConfluenceLevel", back_populates="symbol_obj", cascade="all, delete-orphan"
    )
    strategy_signals: Mapped[list["StrategySignal"]] = relationship(
        "StrategySignal", back_populates="symbol_obj", cascade="all, delete-orphan"
    )


class DailyPrice(Base):
    """Model representing Daily EOD Stock Prices."""

    __tablename__ = "daily_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol_id: Mapped[int] = mapped_column(Integer, ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False)
    trading_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    open: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    adj_close: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BIGINT, nullable=False)
    granularity: Mapped[str] = mapped_column(String(10), nullable=False, default="1d")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())

    # Relationships
    symbol_obj: Mapped["Symbol"] = relationship("Symbol", back_populates="prices")

    __table_args__ = (
        UniqueConstraint("symbol_id", "trading_date", "granularity", name="UQ_Symbol_Date_Granularity"),
        Index("ix_daily_prices_symbol_date", "symbol_id", "trading_date"),
    )


class CorporateAction(Base):
    """Model representing historical corporate actions (splits, dividends)."""

    __tablename__ = "corporate_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol_id: Mapped[int] = mapped_column(Integer, ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False)
    action_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'DIVIDEND', 'SPLIT'
    value: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)  # Dividend amount or split ratio
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())

    # Relationships
    symbol_obj: Mapped["Symbol"] = relationship("Symbol", back_populates="actions")

    __table_args__ = (UniqueConstraint("symbol_id", "action_date", "action_type", name="UQ_Symbol_ActionDate_Type"),)


class SyncJob(Base):
    """Model logging execution sync runs for auditability and recovery."""

    __tablename__ = "sync_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # UUID
    start_time: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    end_time: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # 'RUNNING', 'SUCCESS', 'FAILED', 'PARTIAL'
    total_symbols: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_symbols: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_symbols: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class SymbolSyncState(Base):
    """Model storing last successful sync timestamp per symbol for incremental updates."""

    __tablename__ = "symbol_sync_state"

    symbol_id: Mapped[int] = mapped_column(Integer, ForeignKey("symbols.id", ondelete="CASCADE"), primary_key=True)
    last_successful_sync_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    last_attempt_status: Mapped[str] = mapped_column(String(50), nullable=False)  # 'SUCCESS', 'FAILED'
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    symbol_obj: Mapped["Symbol"] = relationship("Symbol", back_populates="sync_state")


class DailyIndicator(Base):
    """Model representing historical daily technical indicators."""

    __tablename__ = "daily_indicators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol_id: Mapped[int] = mapped_column(Integer, ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False)
    trading_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    granularity: Mapped[str] = mapped_column(String(10), nullable=False, default="1d")

    # Technical Indicators
    rsi_14: Mapped[float | None] = mapped_column(Float, nullable=True)
    atr_14: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma_20: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma_50: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma_200: Mapped[float | None] = mapped_column(Float, nullable=True)
    ema_9: Mapped[float | None] = mapped_column(Float, nullable=True)
    ema_20: Mapped[float | None] = mapped_column(Float, nullable=True)
    ema_21: Mapped[float | None] = mapped_column(Float, nullable=True)
    macd_line: Mapped[float | None] = mapped_column(Float, nullable=True)
    macd_signal: Mapped[float | None] = mapped_column(Float, nullable=True)
    macd_histogram: Mapped[float | None] = mapped_column(Float, nullable=True)
    bb_upper: Mapped[float | None] = mapped_column(Float, nullable=True)
    bb_middle: Mapped[float | None] = mapped_column(Float, nullable=True)
    bb_lower: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Trend strength
    adx_14: Mapped[float | None] = mapped_column(Float, nullable=True)
    plus_di: Mapped[float | None] = mapped_column(Float, nullable=True)
    minus_di: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Volume / accumulation
    obv: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Supertrend(10, 3)
    supertrend: Mapped[float | None] = mapped_column(Float, nullable=True)
    supertrend_dir: Mapped[str | None] = mapped_column(String(10), nullable=True)  # UP / DOWN

    # Stochastic(14, 3, 3)
    stoch_k: Mapped[float | None] = mapped_column(Float, nullable=True)
    stoch_d: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Chaikin Money Flow (20) and Stochastic RSI (14, 14, 3, 3)
    cmf_20: Mapped[float | None] = mapped_column(Float, nullable=True)
    stochrsi_k: Mapped[float | None] = mapped_column(Float, nullable=True)
    stochrsi_d: Mapped[float | None] = mapped_column(Float, nullable=True)
    stochrsi_bullish_xover: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    stochrsi_bearish_xover: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Relationships
    symbol_obj: Mapped["Symbol"] = relationship("Symbol", back_populates="indicators")

    __table_args__ = (
        UniqueConstraint("symbol_id", "trading_date", "granularity", name="UQ_Indicator_Symbol_Date"),
        Index("ix_indicators_symbol_date", "symbol_id", "trading_date"),
    )


class DailyHeikinAshi(Base):
    """Model representing historical daily Heikin-Ashi candles."""

    __tablename__ = "daily_heikin_ashi"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol_id: Mapped[int] = mapped_column(Integer, ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False)
    trading_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    granularity: Mapped[str] = mapped_column(String(10), nullable=False, default="1d")
    open: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)

    # Relationships
    symbol_obj: Mapped["Symbol"] = relationship("Symbol", back_populates="heikin_ashi")

    __table_args__ = (
        UniqueConstraint("symbol_id", "trading_date", "granularity", name="UQ_HA_Symbol_Date"),
        Index("ix_ha_symbol_date", "symbol_id", "trading_date"),
    )


class RenkoBrick(Base):
    """Model representing path-dependent, asynchronous Renko bricks."""

    __tablename__ = "renko_bricks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol_id: Mapped[int] = mapped_column(Integer, ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False)
    brick_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    open: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # 'UP', 'DOWN'
    brick_size: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)

    # Relationships
    symbol_obj: Mapped["Symbol"] = relationship("Symbol", back_populates="renko_bricks")

    __table_args__ = (
        UniqueConstraint("symbol_id", "brick_index", name="UQ_Renko_Symbol_Index"),
        Index("ix_renko_symbol_index", "symbol_id", "brick_index"),
    )


class LineBreakLine(Base):
    """Model representing path-dependent, asynchronous Line Break lines."""

    __tablename__ = "line_break_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol_id: Mapped[int] = mapped_column(Integer, ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False)
    line_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    open: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # 'UP', 'DOWN'

    # Relationships
    symbol_obj: Mapped["Symbol"] = relationship("Symbol", back_populates="line_break_lines")

    __table_args__ = (
        UniqueConstraint("symbol_id", "line_index", name="UQ_LineBreak_Symbol_Index"),
        Index("ix_line_break_symbol_index", "symbol_id", "line_index"),
    )


class ScreeningSnapshot(Base):
    """Model representing optimized, rapid-query latest metrics snapshot for screening."""

    __tablename__ = "screening_snapshots"

    symbol_id: Mapped[int] = mapped_column(Integer, ForeignKey("symbols.id", ondelete="CASCADE"), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_trading_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)

    # Prices
    close_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    price_pct_change: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume: Mapped[int] = mapped_column(BIGINT, nullable=False)

    # Heikin-Ashi Latest
    ha_close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    ha_direction: Mapped[str] = mapped_column(String(10), nullable=False)

    # Indicators Latest
    rsi_14: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma_20_cross_direction: Mapped[str | None] = mapped_column(String(10), nullable=True)
    sma_50_cross_direction: Mapped[str | None] = mapped_column(String(10), nullable=True)
    sma_200_cross_direction: Mapped[str | None] = mapped_column(String(10), nullable=True)
    macd_trend: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Latest Renko Brick Direction
    renko_direction: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Latest Line Break Direction
    line_break_direction: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Pattern Detection Flags
    is_nr7: Mapped[bool | None] = mapped_column(Boolean, nullable=True)        # NR7 — narrowest range of last 7 days
    is_inside_bar: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # Inside bar — range contained within prior bar
    is_gap_up: Mapped[bool | None] = mapped_column(Boolean, nullable=True)     # Today open > prev close by >1%
    is_gap_down: Mapped[bool | None] = mapped_column(Boolean, nullable=True)   # Today open < prev close by >1%

    # Relative Strength vs NIFTY 50
    rs_score_1m: Mapped[float | None] = mapped_column(Float, nullable=True)    # (stock 21D return) / (NIFTY 21D return)

    # MTF / Risk fields (materialized from daily + weekly-resampled data)
    atr_pct: Mapped[float | None] = mapped_column(Float, nullable=True)         # ATR(14) / close * 100
    vol_class: Mapped[str | None] = mapped_column(String(10), nullable=True)    # LOW / MEDIUM / HIGH
    regime_bias: Mapped[str | None] = mapped_column(String(20), nullable=True)  # VERY_BULLISH / BULLISH / NEUTRAL / BEARISH / VERY_BEARISH
    weekly_trend: Mapped[str | None] = mapped_column(String(10), nullable=True) # UP / DOWN (weekly close vs 40-wk EMA)
    mtf_confirmed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # daily bias confirmed by weekly trend

    # Rolling weekly returns (%), 1 week = 5 trading days
    ret_1w: Mapped[float | None] = mapped_column(Float, nullable=True)
    ret_2w: Mapped[float | None] = mapped_column(Float, nullable=True)
    ret_3w: Mapped[float | None] = mapped_column(Float, nullable=True)
    ret_4w: Mapped[float | None] = mapped_column(Float, nullable=True)

    # New indicator snapshot fields
    adx_14: Mapped[float | None] = mapped_column(Float, nullable=True)
    trend_strength_class: Mapped[str | None] = mapped_column(String(10), nullable=True)  # WEAK / MODERATE / STRONG
    obv_trend: Mapped[str | None] = mapped_column(String(10), nullable=True)             # UP / DOWN / FLAT
    supertrend_dir: Mapped[str | None] = mapped_column(String(10), nullable=True)        # UP / DOWN
    stoch_state: Mapped[str | None] = mapped_column(String(15), nullable=True)           # OVERBOUGHT / OVERSOLD / NEUTRAL

    # Volume profile
    weekly_avg_volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_breakout_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Composite scoring (0-100 per component + weighted total)
    composite_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    trend_score_val: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_score_val: Mapped[float | None] = mapped_column(Float, nullable=True)
    rs_score_val: Mapped[float | None] = mapped_column(Float, nullable=True)
    momentum_score_val: Mapped[float | None] = mapped_column(Float, nullable=True)
    cmf_score_val: Mapped[float | None] = mapped_column(Float, nullable=True)
    breakout_score_val: Mapped[float | None] = mapped_column(Float, nullable=True)

    # CMF snapshot
    cmf_20: Mapped[float | None] = mapped_column(Float, nullable=True)
    cmf_20_prev: Mapped[float | None] = mapped_column(Float, nullable=True)
    cmf_crossed_above_zero: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # StochRSI snapshot
    stochrsi_k: Mapped[float | None] = mapped_column(Float, nullable=True)
    stochrsi_d: Mapped[float | None] = mapped_column(Float, nullable=True)
    stochrsi_zone: Mapped[str | None] = mapped_column(String(15), nullable=True)
    stochrsi_bullish_xover_days_ago: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stochrsi_bearish_xover_days_ago: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ML Prediction (written by VajraML post-sync hook, not by the per-symbol screening refresh)
    ml_prediction: Mapped[float | None] = mapped_column(Float, nullable=True)
    ml_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ml_label: Mapped[str | None] = mapped_column(String(20), nullable=True)

    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    symbol_obj: Mapped["Symbol"] = relationship("Symbol", back_populates="screening_snapshot")

    __table_args__ = (
        Index("ix_snapshot_rsi", "rsi_14"),
        Index("ix_snapshot_sma_200", "sma_200_cross_direction"),
        Index("ix_snapshot_bias", "regime_bias"),
        Index("ix_snapshot_cmf", "cmf_20"),
        Index("ix_snapshot_stochrsi_k", "stochrsi_k"),
    )


class MLTrainingRun(Base):
    """Persists each ML model training run — status, metrics, version, timestamps."""

    __tablename__ = "ml_training_runs"

    id:               Mapped[int]                  = mapped_column(Integer, primary_key=True, autoincrement=True)
    version:          Mapped[str]                  = mapped_column(String(30), nullable=False)
    status:           Mapped[str]                  = mapped_column(String(20), nullable=False, default="RUNNING")
    device:           Mapped[str | None]           = mapped_column(String(10), nullable=True)
    num_folds:        Mapped[int | None]           = mapped_column(Integer, nullable=True)
    dataset_rows:     Mapped[int | None]           = mapped_column(Integer, nullable=True)
    date_range_start: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    date_range_end:   Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    mean_ic:          Mapped[float | None]         = mapped_column(Float, nullable=True)
    fold_metrics:     Mapped[str | None]           = mapped_column(Text, nullable=True)   # JSON array
    error_message:    Mapped[str | None]           = mapped_column(Text, nullable=True)
    started_at:       Mapped[datetime.datetime]    = mapped_column(DateTime, default=func.now())
    completed_at:     Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)


class AppSetting(Base):
    """Application settings stored in the database — replaces config.yaml for runtime configuration."""

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)   # AI / DATABASE / MARKET / DOWNLOADER / APPLICATION
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)             # always stored as string
    value_type: Mapped[str] = mapped_column(String(20), nullable=False)  # string / integer / float / boolean / json
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("category", "key", name="UQ_AppSetting_Category_Key"),)


class PortfolioHolding(Base):
    """A single imported portfolio position (e.g. from a Zerodha holdings CSV).

    Replaces the previous browser-localStorage portfolio store — the backend is
    now the single source of truth for holdings and all derived risk metrics.
    """

    __tablename__ = "portfolio_holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument: Mapped[str] = mapped_column(String(50), nullable=False)          # raw ticker e.g. RELIANCE
    symbol_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("symbols.id", ondelete="SET NULL"), nullable=True
    )  # resolved match into the synced universe (nullable — may not exist)
    qty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ltp_imported: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # LTP from the CSV snapshot
    invested: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="zerodha_csv")
    imported_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (
        UniqueConstraint("instrument", name="UQ_PortfolioHolding_Instrument"),
        Index("ix_portfolio_holdings_instrument", "instrument"),
    )


class Alert(Base):
    """A triggered or armed alert for a symbol — evaluated post-sync."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("symbols.id", ondelete="CASCADE"), nullable=True
    )
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(40), nullable=False)
    # PRICE_CROSS_SUPPORT / PRICE_CROSS_RESISTANCE / STOP_HIT / TARGET_HIT /
    # RSI_EXTREME / MACD_CROSS / SUPERTREND_FLIP / VOLUME_BREAKOUT /
    # BIAS_UPGRADE / BIAS_DOWNGRADE
    condition_value: Mapped[float | None] = mapped_column(Float, nullable=True)  # threshold that triggered
    status: Mapped[str] = mapped_column(String(15), nullable=False, default="TRIGGERED")
    # TRIGGERED / DISMISSED
    scope: Mapped[str] = mapped_column(String(15), nullable=False, default="HOLDING")
    # HOLDING / GLOBAL
    message: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (
        Index("ix_alerts_symbol_status", "symbol", "status"),
        Index("ix_alerts_triggered_at", "triggered_at"),
    )


class SymbolConfluenceLevel(Base):
    """Model representing cached backend-calculated Confluence Support and Resistance levels."""

    __tablename__ = "symbol_confluence_levels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol_id: Mapped[int] = mapped_column(Integer, ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False)
    level_type: Mapped[str] = mapped_column(String(10), nullable=False)  # 'SUPPORT' or 'RESISTANCE'
    price: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    strength_score: Mapped[int] = mapped_column(Integer, nullable=False)
    components: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g. "SWING,HVN,EMA200"
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())

    # Relationships
    symbol_obj: Mapped["Symbol"] = relationship("Symbol", back_populates="confluence_levels")

    __table_args__ = (
        Index("ix_confluence_levels_symbol_type", "symbol_id", "level_type"),
    )


class StrategySignal(Base):
    """Materialized latest-bar strategy verdict per symbol (mirrors the Signal schema, §8.1).

    One row per (symbol, strategy). Rebuilt after each sync by StrategyScreenerService,
    exactly like ScreeningSnapshot — so the Strategy screen never does live computation.
    JSON-ish blobs (key_metrics / gates / reasons) are stored as Text for SQLite + MSSQL
    portability and parsed by the API layer.
    """

    __tablename__ = "strategy_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol_id: Mapped[int] = mapped_column(Integer, ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    strategy_id: Mapped[str] = mapped_column(String(50), nullable=False)
    as_of: Mapped[datetime.date] = mapped_column(Date, nullable=False)

    signal: Mapped[str] = mapped_column(String(10), nullable=False)  # BUY / SELL / WATCH / NONE
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_close: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)

    entry_ref: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    initial_stop: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    target: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    risk_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    rr: Mapped[float | None] = mapped_column(Float, nullable=True)

    key_metrics: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    gates: Mapped[str | None] = mapped_column(Text, nullable=True)        # JSON
    reasons: Mapped[str | None] = mapped_column(Text, nullable=True)      # JSON

    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    symbol_obj: Mapped["Symbol"] = relationship("Symbol", back_populates="strategy_signals")

    __table_args__ = (
        UniqueConstraint("symbol_id", "strategy_id", name="UQ_StrategySignal_Symbol_Strategy"),
        Index("ix_strategy_signals_strategy_signal_score", "strategy_id", "signal", "score"),
    )
