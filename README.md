# VajraStocks

A local-first NSE stock analysis platform. Screens, charts, and analyses Indian equities using technical indicators, AI-powered trade plans, and a fast React UI — all running on your machine with no cloud dependency.

---

## Table of Contents
1. [Features](#features)
2. [Architecture](#architecture)
3. [Quick Install](#quick-install)
4. [Manual Setup](#manual-setup)
5. [Configuration](#configuration)
6. [Running the App](#running-the-app)
7. [CLI Reference](#cli-reference)
8. [API Reference](#api-reference)
9. [Database Schema](#database-schema)
10. [Troubleshooting](#troubleshooting)

---

## Features

- **Stock Screener** — Filter NSE equities by RSI, SMA 200, Heikin-Ashi, Renko, Line Break, and volume breakout
- **4 Chart Types** — Candlestick, Heikin-Ashi, Renko, Three Line Break via TradingView Lightweight Charts
- **Technical Indicators** — RSI, ATR, SMA 20/50/200, EMA 9/21, MACD, Bollinger Bands
- **AI Analysis** — Trade plan generation, market regime detection, opportunity scanner (uses local Ollama or any OpenAI-compatible API)
- **Auto Data Sync** — Incremental daily download from Yahoo Finance with rate limiting and retry logic
- **Cross-platform** — Runs on Windows, Linux, and macOS
- **No cloud required** — SQLite by default, optional MSSQL / PostgreSQL

---

## Architecture

```
React 19 + TypeScript (Vite)
        ↕  REST / SSE
FastAPI + Python 3.12
        ↕
SQLAlchemy 2.0  →  SQLite (default) / MSSQL / PostgreSQL
        ↕
Agent Framework  →  Local Ollama / OpenAI-compatible LLM
```

**Directory layout**

```
VajraStocks/
├── frontend/               # React 19 + TypeScript + Vite + Tailwind
│   └── src/
│       ├── components/     # Screener, Charts, Sync, Settings panels
│       ├── store/          # Zustand state
│       └── services/       # API clients
├── python/                 # Python backend
│   ├── src/stocks/
│   │   ├── api/            # FastAPI routes and lifespan
│   │   ├── db/             # SQLAlchemy models, connection manager
│   │   └── services/       # Sync engine, indicators, screening, agents
│   ├── config/             # config.yaml, agent JSON configs
│   ├── migrations/         # Alembic migration scripts
│   └── pyproject.toml
├── installer/              # Platform installer scripts and PyInstaller spec
└── .github/workflows/      # CI/CD — build, test, release
```

---

## Quick Install

Download the latest installer from the [Releases page](https://github.com/abhishek4official/VajraStocks/releases).

| Platform | File |
|----------|------|
| Windows 10/11 | `VajraStocks-Setup.exe` |
| Linux (Debian/Ubuntu) | `VajraStocks.deb` |
| Linux (Fedora/RHEL) | `VajraStocks.rpm` |
| Linux (Universal) | `VajraStocks.AppImage` |
| macOS 12+ | `VajraStocks.dmg` |

No Python or Node.js installation required — everything is bundled.

### Windows
Run `VajraStocks-Setup.exe` and follow the wizard. A desktop shortcut is created automatically.

### Linux (.deb)
```bash
sudo dpkg -i VajraStocks.deb
vajrastocks
```

### Linux (.AppImage)
```bash
chmod +x VajraStocks.AppImage
./VajraStocks.AppImage
```
> [!NOTE]
> Modern distributions (like Ubuntu 22.04+ or Debian 12+) do not include `libfuse2` by default. If the AppImage fails to launch, install the FUSE compatibility library using:
> `sudo apt install -y libfuse2`
> Alternatively, you can run the AppImage without FUSE by extracting it first:
> `./VajraStocks.AppImage --appimage-extract`
> `cd squashfs-root && ./AppRun`

### macOS
Open `VajraStocks.dmg`, drag to Applications, and launch. 
*(If the release build is run from a fork or local machine without Apple Developer ID signing certificates, you may need to right-click the app icon and select "Open" on first launch to bypass macOS Gatekeeper).*

The app opens at `http://localhost:8000` in your default browser.

---

## Manual Setup

Use this if you want to run from source or contribute.

### Requirements
- Python 3.12 (use [uv](https://github.com/astral-sh/uv) — `pip install uv`)
- Node.js 18+

### Backend

```bash
cd python
uv sync
uv run alembic upgrade head
```

### Frontend

```bash
cd frontend
npm install
npm run build
```

### Start

```bash
# From the repo root
cd python
uv run uvicorn stocks.api.main:app --host 127.0.0.1 --port 8000
```

Open [http://localhost:8000](http://localhost:8000).

For frontend development with hot reload:

```bash
cd frontend
npm run dev   # runs on http://localhost:5173
```

---

## Configuration

Configuration is stored in `python/config/config.yaml`. The most common settings:

```yaml
database:
  # Default — SQLite, no setup needed
  connection_string: "sqlite:///data/vajra.db"

  # Optional — switch to MSSQL after install via Settings UI
  # connection_string: "mssql+pyodbc://(localdb)\\MSSQLLocalDB/vajra_stocks?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes"

downloader:
  history_years: 3       # Years of price history to download
  batch_size: 50         # Symbols per Yahoo Finance batch

ai:
  provider: ollama
  base_url: http://localhost:11434   # Your Ollama server address
  model: qwen2.5-coder:7b
```

Settings can also be changed at runtime from the **Settings** panel in the UI — no restart needed for most options.

### Switching database
Go to **Settings → Database**, enter your connection string, and click Save. The app restarts the connection automatically. Your data directory is:

- Windows: `%APPDATA%\VajraStocks\data`
- macOS: `~/Library/Application Support/VajraStocks/data`
- Linux: `~/.local/share/VajraStocks/data`

---

## Running the App

### Installed version
Launch from the Desktop shortcut (Windows), Applications folder (macOS), or run `vajrastocks` in a terminal (Linux).

### From source
```bash
cd python
uv run uvicorn stocks.api.main:app --host 127.0.0.1 --port 8000
```

Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## CLI Reference

The `nse-downloader` CLI runs headless database operations:

```bash
# Sync all active symbols (incremental)
uv run nse-downloader sync

# Sync specific symbols
uv run nse-downloader sync --symbols "RELIANCE,TCS,INFY"

# Refresh NSE equity list from official source
uv run nse-downloader bootstrap-symbols

# View recent sync job history
uv run nse-downloader status --limit 10

# Recalculate all technical indicators from stored prices
uv run nse-downloader recalculate-derived

# Run a screen directly from the CLI
uv run nse-downloader screen --max-rsi 30 --sma-200-cross ABOVE
```

---

## API Reference

All endpoints are prefixed with `/api/v1`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/symbols` | List all registered NSE symbols |
| GET | `/charts/{symbol}/candles` | OHLCV candlestick data |
| GET | `/charts/{symbol}/heikin-ashi` | Heikin-Ashi candles |
| GET | `/charts/{symbol}/renko` | Renko bricks |
| GET | `/charts/{symbol}/line-break` | Three Line Break lines |
| GET | `/indicators/{symbol}` | RSI, MACD, SMA, Bollinger Bands |
| GET | `/screeners` | Run screener with filter params |
| POST | `/sync/full` | Trigger full incremental sync |
| POST | `/sync/symbol/{symbol}` | Sync a single symbol |
| GET | `/sync/jobs` | Sync job history |
| GET | `/agents/chat-stream` | SSE stream — AI analysis |
| GET | `/settings` | Read all settings |
| PUT | `/settings` | Update settings |

Full interactive docs at [http://localhost:8000/docs](http://localhost:8000/docs).

---

## Database Schema

```
symbols ──< daily_prices
        ──< daily_indicators
        ──< daily_heikin_ashi
        ──< renko_bricks
        ──< line_break_lines
        ──< corporate_actions
        ──1 screening_snapshots   (pre-computed cache for fast screening)
        ──1 symbol_sync_state     (tracks last sync date per symbol)
```

`screening_snapshots` is rebuilt after every sync — it stores one row per active symbol with all latest indicator values so screener queries never do live joins.

---

## Troubleshooting

**App won't start / port in use**
The app automatically tries ports 8000–8019. If all are busy, check `~/.local/share/VajraStocks/` (Linux) or `%APPDATA%\VajraStocks\` (Windows) for logs.

**Database connection error**
Open Settings → Database and verify your connection string. The app always falls back to SQLite if the configured database is unreachable.

**MSSQL / ODBC errors on Windows**
Install [Microsoft ODBC Driver 17 for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server) and ensure LocalDB is running:
```powershell
sqllocaldb start MSSQLLocalDB
```

**Yahoo Finance rate limit (HTTP 429)**
Reduce `batch_size` in `config.yaml` to `20` and wait a few minutes before retrying.

**Ollama model not found**
```bash
ollama pull qwen2.5-coder:7b
```
Verify the `base_url` in Settings matches your Ollama server address.

**macOS Gatekeeper warning**
Right-click the app → Open on first launch. This is expected for unsigned builds.

---

## License

MIT
