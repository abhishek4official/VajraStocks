import datetime
from typing import List, Optional
from sqlalchemy import (
    BIGINT,
    Boolean,
    DECIMAL,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    NVARCHAR,
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
    symbol: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, unique=True, index=True)
    company_name: Mapped[str] = mapped_column(NVARCHAR(255), nullable=False)
    isin: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, unique=True)
    series: Mapped[str] = mapped_column(NVARCHAR(10), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    prices: Mapped[List["DailyPrice"]] = relationship(
        "DailyPrice", back_populates="symbol_obj", cascade="all, delete-orphan"
    )
    actions: Mapped[List["CorporateAction"]] = relationship(
        "CorporateAction", back_populates="symbol_obj", cascade="all, delete-orphan"
    )
    sync_state: Mapped[Optional["SymbolSyncState"]] = relationship(
        "SymbolSyncState", back_populates="symbol_obj", uselist=False, cascade="all, delete-orphan"
    )
    indicators: Mapped[List["DailyIndicator"]] = relationship(
        "DailyIndicator", back_populates="symbol_obj", cascade="all, delete-orphan"
    )
    heikin_ashi: Mapped[List["DailyHeikinAshi"]] = relationship(
        "DailyHeikinAshi", back_populates="symbol_obj", cascade="all, delete-orphan"
    )
    renko_bricks: Mapped[List["RenkoBrick"]] = relationship(
        "RenkoBrick", back_populates="symbol_obj", cascade="all, delete-orphan"
    )
    line_break_lines: Mapped[List["LineBreakLine"]] = relationship(
        "LineBreakLine", back_populates="symbol_obj", cascade="all, delete-orphan"
    )
    screening_snapshot: Mapped[Optional["ScreeningSnapshot"]] = relationship(
        "ScreeningSnapshot", back_populates="symbol_obj", uselist=False, cascade="all, delete-orphan"
    )

class DailyPrice(Base):
    """Model representing Daily EOD Stock Prices."""
    __tablename__ = "daily_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol_id: Mapped[int] = mapped_column(Integer, ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False)
    trading_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    open: Mapped[float] = mapped_column(DECIMAL(18, 4), nullable=False)
    high: Mapped[float] = mapped_column(DECIMAL(18, 4), nullable=False)
    low: Mapped[float] = mapped_column(DECIMAL(18, 4), nullable=False)
    close: Mapped[float] = mapped_column(DECIMAL(18, 4), nullable=False)
    adj_close: Mapped[float] = mapped_column(DECIMAL(18, 4), nullable=False)
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
    action_type: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False)  # 'DIVIDEND', 'SPLIT'
    value: Mapped[float] = mapped_column(DECIMAL(18, 4), nullable=False)     # Dividend amount or split ratio
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())

    # Relationships
    symbol_obj: Mapped["Symbol"] = relationship("Symbol", back_populates="actions")

    __table_args__ = (
        UniqueConstraint("symbol_id", "action_date", "action_type", name="UQ_Symbol_ActionDate_Type"),
    )

class SyncJob(Base):
    """Model logging execution sync runs for auditability and recovery."""
    __tablename__ = "sync_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # UUID
    start_time: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    end_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False)  # 'RUNNING', 'SUCCESS', 'FAILED', 'PARTIAL'
    total_symbols: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_symbols: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_symbols: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

class SymbolSyncState(Base):
    """Model storing last successful sync timestamp per symbol for incremental updates."""
    __tablename__ = "symbol_sync_state"

    symbol_id: Mapped[int] = mapped_column(Integer, ForeignKey("symbols.id", ondelete="CASCADE"), primary_key=True)
    last_successful_sync_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    last_attempt_status: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False)  # 'SUCCESS', 'FAILED'
    last_error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
    rsi_14: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    atr_14: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sma_20: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sma_50: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sma_200: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ema_9: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ema_21: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    macd_line: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    macd_signal: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    macd_histogram: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bb_upper: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bb_middle: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bb_lower: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

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
    open: Mapped[float] = mapped_column(DECIMAL(12, 4), nullable=False)
    high: Mapped[float] = mapped_column(DECIMAL(12, 4), nullable=False)
    low: Mapped[float] = mapped_column(DECIMAL(12, 4), nullable=False)
    close: Mapped[float] = mapped_column(DECIMAL(12, 4), nullable=False)

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
    open: Mapped[float] = mapped_column(DECIMAL(12, 4), nullable=False)
    close: Mapped[float] = mapped_column(DECIMAL(12, 4), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # 'UP', 'DOWN'
    brick_size: Mapped[float] = mapped_column(DECIMAL(12, 4), nullable=False)

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
    open: Mapped[float] = mapped_column(DECIMAL(12, 4), nullable=False)
    close: Mapped[float] = mapped_column(DECIMAL(12, 4), nullable=False)
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
    symbol: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False)
    company_name: Mapped[str] = mapped_column(NVARCHAR(255), nullable=False)
    last_trading_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)

    # Prices
    close_price: Mapped[float] = mapped_column(DECIMAL(12, 4), nullable=False)
    price_pct_change: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume: Mapped[int] = mapped_column(BIGINT, nullable=False)

    # Heikin-Ashi Latest
    ha_close: Mapped[float] = mapped_column(DECIMAL(12, 4), nullable=False)
    ha_direction: Mapped[str] = mapped_column(String(10), nullable=False)

    # Indicators Latest
    rsi_14: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sma_20_cross_direction: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    sma_50_cross_direction: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    sma_200_cross_direction: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    macd_trend: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Latest Renko Brick Direction
    renko_direction: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Latest Line Break Direction
    line_break_direction: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    symbol_obj: Mapped["Symbol"] = relationship("Symbol", back_populates="screening_snapshot")

    __table_args__ = (
        Index("ix_snapshot_rsi", "rsi_14"),
        Index("ix_snapshot_sma_200", "sma_200_cross_direction"),
    )
