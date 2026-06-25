"""DuckDB + partitioned-Parquet bar store — the analytical data plane for V2.

Large time-series (daily/intraday/tick OHLCV) live here as immutable Parquet, partitioned
``symbol=<sym>/year=<yyyy>`` so a query for one symbol/year prunes to just those files.
SQLite stays the transactional/state store; this layer is append-heavy and read-mostly.

Adjustments are applied at query time (``read_bars(adjusted=True, actions=...)``) so a
corporate action never rewrites historical partitions.

See Doc/VajraStocks_V2.0_PRD_BRD_Architecture.md §3A, §17, §18.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import duckdb
import pandas as pd

from stocks.data.adjustments import _as_date, apply_split_adjustments

if TYPE_CHECKING:
    from stocks.config import Config

DATA_COLUMNS = ["trading_date", "open", "high", "low", "close", "adj_close", "volume"]


class BarStore:
    """Columnar OHLCV store backed by Hive-partitioned Parquet, queried via DuckDB."""

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_config(cls, config: Config) -> BarStore:
        """Construct from the app Config (``storage.columnar_data_dir``)."""
        return cls(config.storage.columnar_data_dir)

    # ── paths ────────────────────────────────────────────────────────────────

    def _granularity_dir(self, granularity: str) -> Path:
        return self.data_dir / "bars" / f"granularity={granularity}"

    def _symbol_dir(self, symbol: str, granularity: str) -> Path:
        return self._granularity_dir(granularity) / f"symbol={symbol}"

    def _partition_file(self, symbol: str, year: int, granularity: str) -> Path:
        return self._symbol_dir(symbol, granularity) / f"year={year}" / "data.parquet"

    # ── write ────────────────────────────────────────────────────────────────

    def write_bars(self, symbol: str, bars: pd.DataFrame, granularity: str = "1d") -> int:
        """Upsert ``bars`` for ``symbol`` (keyed by trading_date). Returns rows written.

        Re-writing an existing date replaces it; new dates are appended. Only the
        ``year`` partitions touched by the input are rewritten.
        """
        if bars.empty:
            return 0

        df = bars.copy()
        df["trading_date"] = df["trading_date"].map(_as_date)
        for col in DATA_COLUMNS:
            if col not in df.columns:
                raise ValueError(f"write_bars: missing required column {col!r}")
        df = df[DATA_COLUMNS]
        df["volume"] = df["volume"].astype("int64")

        written = 0
        for year, group in df.groupby(df["trading_date"].map(lambda d: d.year)):
            file = self._partition_file(symbol, int(year), granularity)
            file.parent.mkdir(parents=True, exist_ok=True)

            if file.exists():
                existing = pd.read_parquet(file)
                existing["trading_date"] = existing["trading_date"].map(_as_date)
                combined = pd.concat([existing, group], ignore_index=True)
            else:
                combined = group

            combined = (
                combined.drop_duplicates(subset="trading_date", keep="last")
                .sort_values("trading_date")
                .reset_index(drop=True)
            )
            combined.to_parquet(file, index=False)
            written += len(group)

        return written

    # ── read ─────────────────────────────────────────────────────────────────

    def read_bars(
        self,
        symbol: str,
        start: dt.date | None = None,
        end: dt.date | None = None,
        granularity: str = "1d",
        adjusted: bool = False,
        actions: Sequence[dict[str, Any]] | None = None,
    ) -> pd.DataFrame:
        """Return bars for ``symbol`` sorted by trading_date, optionally back-adjusted.

        ``start``/``end`` are inclusive. Year partitions outside the range are pruned at
        the file-selection level before DuckDB scans them.
        """
        sdir = self._symbol_dir(symbol, granularity)
        if not sdir.exists():
            return pd.DataFrame(columns=DATA_COLUMNS)

        # Partition pruning: only scan year dirs overlapping [start, end].
        lo = start.year if start else None
        hi = end.year if end else None
        files: list[str] = []
        for year_dir in sorted(sdir.glob("year=*")):
            try:
                year = int(year_dir.name.split("=", 1)[1])
            except (IndexError, ValueError):
                continue
            if (lo is not None and year < lo) or (hi is not None and year > hi):
                continue
            pq = year_dir / "data.parquet"
            if pq.exists():
                files.append(pq.as_posix())

        if not files:
            return pd.DataFrame(columns=DATA_COLUMNS)

        con = duckdb.connect()
        try:
            df = con.execute(
                "SELECT * FROM read_parquet(?) ORDER BY trading_date", [files]
            ).fetchdf()
        finally:
            con.close()

        df["trading_date"] = pd.to_datetime(df["trading_date"]).dt.date
        if start is not None:
            df = df[df["trading_date"] >= start]
        if end is not None:
            df = df[df["trading_date"] <= end]
        df["volume"] = df["volume"].astype("int64")
        df = df[DATA_COLUMNS].sort_values("trading_date").reset_index(drop=True)

        if adjusted and actions:
            df = apply_split_adjustments(df, actions)

        return df

    # ── catalog ──────────────────────────────────────────────────────────────

    def list_symbols(self, granularity: str = "1d") -> list[str]:
        """Return the symbols that have data for the given granularity."""
        gdir = self._granularity_dir(granularity)
        if not gdir.exists():
            return []
        return sorted(
            d.name.split("=", 1)[1] for d in gdir.glob("symbol=*") if d.is_dir()
        )
