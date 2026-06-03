# VajraStocks — Python Backend

FastAPI + SQLAlchemy backend for the VajraStocks NSE analysis platform.

This is the Python implementation. See the repository root `README.md` for the
full project overview, and `dotnet/docs/` for the .NET Core migration guides.

## Run

```powershell
# from the repo root
.\start.ps1
```

Or directly:

```powershell
cd python
uv sync
.venv\Scripts\python.exe -m uvicorn stocks.api.main:app --host 127.0.0.1 --port 8000
```

## Layout

```
python/
├── src/stocks/        # application package
│   ├── api/           # FastAPI routes + lifespan
│   ├── db/            # SQLAlchemy models + connection
│   ├── services/      # sync, indicators, screening, agents, settings
│   └── utils/
├── migrations/        # Alembic migrations
├── config/            # config.yaml
├── tests/
├── scripts/
├── data/              # SQLite db (when used)
└── pyproject.toml
```
