"""Columnar analytical data plane (V2 hybrid-DB).

Houses the DuckDB + partitioned-Parquet store for large time-series (OHLCV / tick /
features) and the query-time corporate-action adjustment logic. SQLite remains the
transactional/state store; this package is read-mostly and append-heavy.

See Doc/VajraStocks_V2.0_PRD_BRD_Architecture.md §3A, §17, §18.
"""
