# VajraStocks — Run Notes & Context

_Last updated: 2026-06-04_

## Current State (Reartecture branch)

Phase 1 Foundation is **complete and committed**:
- SQLite support (multi-provider DB abstraction)
- DB-backed settings (`app_settings` table + SettingsService)
- First-run setup wizard (`SetupWizard.tsx`)
- Settings UI page (`SettingsPanel.tsx`)
- FastAPI lifespan (no more module-level init crash)
- FastAPI serves the React build at one port (StaticFiles + SPA catch-all)
- `install.ps1` + `start.ps1` Windows scripts

## CRITICAL: Two project copies exist on disk

| Path | Status |
|------|--------|
| `C:\Users\abhis\Documents\VajraStocks` | **THE REAL ONE** — git repo, all current work |
| `C:\Users\abhis\Documents\Workspace\VajraAgent\Stocks` | OLD COPY — stale code, DO NOT USE |

The OLD copy's venv has a `stocks.pth` pointing to its own stale `src/`.
If a server loads from there, you get the old code (404 on `/`, health shows
`app_name: nse-historical-downloader`).

## How to tell which code is running

```
curl http://localhost:8000/health
```
- NEW (correct):  `{"status":"HEALTHY","version":"1.0.0"}`
- OLD (stale):    `{"status":"HEALTHY","app_name":"nse-historical-downloader",...}`

## How to run CORRECTLY

Always from the real project dir, using ITS OWN venv:

```powershell
cd C:\Users\abhis\Documents\VajraStocks
.\start.ps1
```

Or explicitly:
```powershell
cd C:\Users\abhis\Documents\VajraStocks
.\.venv\Scripts\python.exe -m uvicorn stocks.api.main:app --host 127.0.0.1 --port 8000
```

Then open: http://localhost:8000

## Database

Currently using **MSSQL** (from `config/config.yaml`). All existing NSE data
intact. The `app_settings` table is auto-created on startup.
To switch to SQLite: change `db_connection_string` in the Settings tab
(starts empty — would need re-sync).

## TODO / Next (Phase 2)

Persist Portfolio, Watchlist, Alerts to DB (currently localStorage).
