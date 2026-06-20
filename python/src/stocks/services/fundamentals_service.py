"""Fetches and caches fundamental data from yfinance for NSE symbols."""

from __future__ import annotations

import datetime

import yfinance as yf
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from stocks.db.models import Symbol, SymbolFundamentals

# Re-fetch fundamentals only when older than this many days
_STALE_DAYS = 7


class FundamentalsService:
    def __init__(self, db: Session):
        self.db = db

    def get(self, symbol: str) -> dict | None:
        """Return cached fundamentals for a symbol, or None if never fetched."""
        row = self.db.scalar(select(SymbolFundamentals).where(SymbolFundamentals.symbol == symbol))
        if row is None:
            return None
        return self._to_dict(row)

    def fetch_and_store(self, symbol_id: int, symbol: str) -> dict | None:
        """Fetch from yfinance and upsert into DB. Returns the dict or None on failure."""
        ticker_sym = symbol if symbol.endswith(".NS") else f"{symbol}.NS"
        try:
            info = yf.Ticker(ticker_sym).info
        except Exception as e:
            logger.warning(f"Fundamentals fetch failed for {symbol}: {e}")
            return None

        if not info or info.get("quoteType") is None:
            logger.warning(f"Fundamentals: empty info for {symbol}")
            return None

        def _f(key: str) -> float | None:
            v = info.get(key)
            if v is None:
                return None
            import math
            f = float(v)
            return None if not math.isfinite(f) else f

        existing = self.db.scalar(select(SymbolFundamentals).where(SymbolFundamentals.symbol_id == symbol_id))

        data = dict(
            symbol_id=symbol_id,
            symbol=symbol,
            market_cap=_f("marketCap"),
            enterprise_value=_f("enterpriseValue"),
            pe_ratio=_f("trailingPE"),
            forward_pe=_f("forwardPE"),
            pb_ratio=_f("priceToBook"),
            ev_ebitda=_f("enterpriseToEbitda"),
            price_to_sales=_f("priceToSalesTrailing12Months"),
            revenue_ttm=_f("totalRevenue"),
            net_profit_ttm=_f("netIncomeToCommon"),
            ebitda=_f("ebitda"),
            gross_margin=_f("grossMargins"),
            profit_margin=_f("profitMargins"),
            operating_margin=_f("operatingMargins"),
            eps_ttm=_f("trailingEps"),
            book_value=_f("bookValue"),
            dividend_yield=_f("dividendYield"),
            roe=_f("returnOnEquity"),
            roa=_f("returnOnAssets"),
            debt_to_equity=_f("debtToEquity"),
            current_ratio=_f("currentRatio"),
            free_cashflow=_f("freeCashflow"),
            sector=info.get("sector"),
            industry=info.get("industry"),
            fetched_at=datetime.datetime.now(),
        )

        if existing is None:
            self.db.add(SymbolFundamentals(**data))
        else:
            for k, v in data.items():
                setattr(existing, k, v)

        self.db.commit()
        logger.info(f"Fundamentals stored for {symbol}")
        return self._to_dict(existing if existing else self.db.scalar(
            select(SymbolFundamentals).where(SymbolFundamentals.symbol_id == symbol_id)
        ))

    def get_or_fetch(self, symbol_id: int, symbol: str) -> dict | None:
        """Return cached data; re-fetch from yfinance if stale or missing."""
        row = self.db.scalar(select(SymbolFundamentals).where(SymbolFundamentals.symbol_id == symbol_id))
        if row is not None:
            age = (datetime.datetime.now() - row.fetched_at).days
            if age < _STALE_DAYS:
                return self._to_dict(row)
        return self.fetch_and_store(symbol_id, symbol)

    def refresh_all(self, limit: int = 200) -> int:
        """Batch-refresh fundamentals for all synced symbols. Returns count updated."""
        syms = self.db.execute(
            select(Symbol.id, Symbol.symbol).where(Symbol.is_active == True).limit(limit)
        ).all()
        updated = 0
        for sym_id, sym in syms:
            try:
                result = self.fetch_and_store(sym_id, sym)
                if result:
                    updated += 1
            except Exception as e:
                logger.warning(f"Fundamentals refresh failed for {sym}: {e}")
        return updated

    @staticmethod
    def _to_dict(row: SymbolFundamentals) -> dict:
        return {
            "symbol": row.symbol,
            "market_cap": row.market_cap,
            "enterprise_value": row.enterprise_value,
            "pe_ratio": row.pe_ratio,
            "forward_pe": row.forward_pe,
            "pb_ratio": row.pb_ratio,
            "ev_ebitda": row.ev_ebitda,
            "price_to_sales": row.price_to_sales,
            "revenue_ttm": row.revenue_ttm,
            "net_profit_ttm": row.net_profit_ttm,
            "ebitda": row.ebitda,
            "gross_margin": row.gross_margin,
            "profit_margin": row.profit_margin,
            "operating_margin": row.operating_margin,
            "eps_ttm": row.eps_ttm,
            "book_value": row.book_value,
            "dividend_yield": row.dividend_yield,
            "roe": row.roe,
            "roa": row.roa,
            "debt_to_equity": row.debt_to_equity,
            "current_ratio": row.current_ratio,
            "free_cashflow": row.free_cashflow,
            "sector": row.sector,
            "industry": row.industry,
            "fetched_at": row.fetched_at.isoformat() if row.fetched_at else None,
        }
