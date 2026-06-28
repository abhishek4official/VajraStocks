"""Background job queue (V2.0 spec M1).

Moves long-running work (sync, indicator recompute, backtests, backfill) off the request
thread into a DB-backed queue with progress, cancel, and retry — so the app stays
responsive instead of stalling on a startup sync. See runner.py.
"""
