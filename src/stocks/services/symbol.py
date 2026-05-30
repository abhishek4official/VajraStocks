import csv
import io
import requests
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select
from loguru import logger
from pathlib import Path
from stocks.config import Config
from stocks.db.models import Symbol
from stocks.utils.exceptions import ValidationError

class SymbolService:
    """Service to fetch, parse, and synchronize active stock symbols from the NSE India website into the database."""
    
    def __init__(self, config: Config, db_session: Session):
        self.config = config
        self.db = db_session
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }

    def fetch_active_symbols_from_nse(self) -> List[Dict[str, str]]:
        """Downloads the active equities list CSV directly from NSE India with fallback support."""
        url = self.config.symbols.active_equities_url
        logger.info(f"Fetching active stock symbols from NSE website: {url}")
        
        try:
            # We use a requests session with browser headers to avoid automated scrape blocks
            with requests.Session() as session:
                response = session.get(url, headers=self.headers, timeout=self.config.downloader.timeout_seconds)
                response.raise_for_status()
                
                # Parse content
                csv_data = response.content.decode("utf-8")
                return self._parse_csv_content(csv_data)
                
        except Exception as e:
            logger.error(f"Failed to fetch active stock symbols from NSE URL: {e}. Attempting fallback...")
            return self._fetch_from_fallback()

    def _fetch_from_fallback(self) -> List[Dict[str, str]]:
        """Fallback method to load locally cached EQUITY_L_ACTIVE.csv."""
        fallback_path = Path(self.config.symbols.fallback_csv_path)
        logger.info(f"Attempting to load fallback symbols from: {fallback_path.resolve()}")
        
        if not fallback_path.exists():
            logger.error(f"Fallback CSV file not found at {fallback_path}")
            raise ValidationError("No active symbol list found (both NSE URL download and local fallback CSV failed).")
            
        with open(fallback_path, mode="r", encoding="utf-8") as f:
            csv_data = f.read()
        return self._parse_csv_content(csv_data)

    def _parse_csv_content(self, csv_content: str) -> List[Dict[str, str]]:
        """Parses the raw EQUITY_L_ACTIVE.csv text content into standardized dictionaries."""
        parsed_symbols = []
        
        # Read using CSV module
        f = io.StringIO(csv_content.strip())
        reader = csv.reader(f)
        
        try:
            headers = next(reader)
        except StopIteration:
            raise ValidationError("CSV content is empty.")
            
        # Clean headers (strip spaces, uppercase)
        headers = [h.strip().upper() for h in headers]
        
        # Verify required columns exist
        required_cols = ["SYMBOL", "NAME OF COMPANY", "SERIES", "ISIN NUMBER"]
        for col in required_cols:
            if col not in headers:
                raise ValidationError(f"Invalid NSE Equities CSV format. Missing required column: {col}")
                
        symbol_idx = headers.index("SYMBOL")
        name_idx = headers.index("NAME OF COMPANY")
        series_idx = headers.index("SERIES")
        isin_idx = headers.index("ISIN NUMBER")
        
        for row in reader:
            if not row or len(row) <= max(symbol_idx, name_idx, series_idx, isin_idx):
                continue
                
            symbol = row[symbol_idx].strip()
            name = row[name_idx].strip()
            series = row[series_idx].strip()
            isin = row[isin_idx].strip()
            
            # Basic validation: ensure key fields are not empty
            if symbol and name and isin:
                # Yahoo Finance format for NSE stocks: Append '.NS'
                yf_symbol = f"{symbol}.NS"
                parsed_symbols.append({
                    "symbol": yf_symbol,
                    "company_name": name,
                    "series": series,
                    "isin": isin
                })
                
        logger.info(f"Successfully parsed {len(parsed_symbols)} symbols from CSV.")
        return parsed_symbols

    def sync_symbols(self, symbols_data: List[Dict[str, str]]) -> int:
        """Synchronizes symbols list with the database (inserts new, updates existing, handles delistings)."""
        logger.info(f"Synchronizing {len(symbols_data)} symbols with local database...")
        
        try:
            # Query existing symbols from database to check for updates and minimize roundtrips
            existing_symbols_query = self.db.scalars(select(Symbol)).all()
            db_symbols_by_name = {s.symbol: s for s in existing_symbols_query}
            
            inserted_count = 0
            updated_count = 0
            active_symbols = set()
            
            for item in symbols_data:
                sym_str = item["symbol"]
                active_symbols.add(sym_str)
                
                if sym_str in db_symbols_by_name:
                    # Update existing record
                    db_sym = db_symbols_by_name[sym_str]
                    db_sym.company_name = item["company_name"]
                    db_sym.isin = item["isin"]
                    db_sym.series = item["series"]
                    db_sym.is_active = True
                    updated_count += 1
                else:
                    # Insert new record
                    new_sym = Symbol(
                        symbol=sym_str,
                        company_name=item["company_name"],
                        isin=item["isin"],
                        series=item["series"],
                        is_active=True
                    )
                    self.db.add(new_sym)
                    inserted_count += 1
            
            # Mark symbols no longer present in the active list as inactive (safeguard for delistings)
            inactive_count = 0
            for sym_str, db_sym in db_symbols_by_name.items():
                if sym_str not in active_symbols and db_sym.is_active:
                    db_sym.is_active = False
                    inactive_count += 1
            
            self.db.commit()
            logger.info(
                f"Symbol synchronization complete. "
                f"Inserted: {inserted_count}, Updated: {updated_count}, Marked Inactive: {inactive_count}."
            )
            return inserted_count + updated_count
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error synchronizing symbols with database: {e}")
            raise ValidationError(f"Database symbol sync failed: {e}") from e
