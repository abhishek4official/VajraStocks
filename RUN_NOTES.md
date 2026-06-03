# VajraStocks — Run Notes & Context

_Last updated: 2026-06-04_

## Repository layout (segregated)

```
VajraStocks/
├── python/                 # Python backend (FastAPI + SQLAlchemy)
│   ├── src/stocks/
│   ├── migrations/
│   ├── config/
│   ├── tests/  scripts/  data/  logs/
│   ├── pyproject.toml  uv.lock  alembic.ini
│   └── .venv/              # created by `uv sync` (run from python/)
├── frontend/               # React 19 + Vite
├── dotnet/                 # .NET Core migration target
│   └── docs/               # MIGRATION_GUIDE.md + IMPLEMENTATION_GUIDE.md
├── agent-framework-source-tmp/   # MAF Python reference (read-only)
├── vajra_stocks_flutter/   # Flutter (ignored)
├── install.ps1  start.ps1  # launchers (operate on python/ + frontend/)
└── README.md  RUN_NOTES.md  LICENSE
```

## How to run

```powershell
cd C:\Users\abhis\Documents\VajraStocks
.\start.ps1
```
Opens http://localhost:8000 (hard-refresh Ctrl+Shift+R after a rebuild).

`start.ps1` cd's into `python/` and uses `python/.venv\Scripts\python.exe` directly,
so it always loads the correct backend (never a stale copy).

## Rebuild after code changes

- Backend: just restart `start.ps1` (uvicorn picks up `python/src`).
- Frontend: `cd frontend; npm run build` — FastAPI serves the new `frontend/dist`.

## Database

Currently **MSSQL LocalDB** (`(localdb)\MSSQLLocalDB` → `NSEStockData`, 2,367 symbols).
Connection string is in `python/config/config.yaml`.
- The app auto-starts LocalDB on boot (`ensure_localdb_started`).
- `app_settings` table is auto-created on startup (idempotent).
- To go fully local: switch the connection string to `sqlite:///data/vajra.db`
  (a migration script exists at `python/scripts/migrate_mssql_to_sqlite.py`).

## CRITICAL: stale duplicate copy

A second OLD copy exists at:
`C:\Users\abhis\Documents\Workspace\VajraAgent\Stocks`
Its venv's `stocks.pth` points to its own stale `src/`. Never run from there.
Tell-tale of wrong code: `curl /health` shows `app_name: nse-historical-downloader`
instead of `version: 1.0.0`.

## .NET migration

See `dotnet/docs/`:
- `MIGRATION_GUIDE.md` — strategy, component mapping, phased roadmap, risks
- `IMPLEMENTATION_GUIDE.md` — solution structure, .proto contracts, EF Core,
  gRPC services, MAF .NET agents, Yahoo Finance client, Hangfire, frontend gRPC-Web

## Next (Phase 2, Python side)

Persist Portfolio, Watchlist, Alerts to DB (currently localStorage).
