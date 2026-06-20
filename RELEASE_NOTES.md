# VajraStocks v1.5.0

**Release Date:** June 2026

---

## What's New in v1.5.0

### VajraML2 — New ML Engine
- Replaced VajraML V1 with VajraML2: triple-barrier classifier with walk-forward validation
- Inference filters to suppress low-confidence signals
- Final production model retrained on full history after walk-forward evaluation
- Weekly automated ML retraining via the scheduler
- Prediction dataset limited to last 400 days for faster rebuilds

### Charting
- Interactive **Trend Lines** — draw, drag, and persist trendlines directly on price charts

### Analytics
- **Rolling Alpha** (1W / 4W / 3M) calculated for every symbol in the database
- Watchlist persistence in the database — survives app restarts

### AI & Agents
- Fixed agent workflow and agent panel stability issues
- Fixed AI Screener screen

### Screeners & Strategies
- 14 new MA / MACD / CMF crossover features added to the screener engine
- Fixed screener result rendering and filter state

### Bug Fixes
- Clamp `inf`/`NaN` fundamentals to `None` before MSSQL insert (prevents type errors on SQL Server)
- Remove stale `ml-training` tab from initial tab list
- Various workflow and sync stability fixes

---

## What's New in v1.0.0 – v1.4.0

### Installer & Distribution
- One-click installer for Windows (`VajraStocks-Setup.exe`), Linux (`.deb`, `.rpm`, `.AppImage`), and macOS (`.dmg`)
- No Python or Node.js installation required — everything is bundled
- Automatic browser launch on startup at `http://localhost:8000`
- Data stored in a user-writable location (`%APPDATA%\VajraStocks` on Windows)

### Stock Screening
- Screen NSE equities by RSI, SMA 200 crossover, Heikin-Ashi direction, Renko, and Line Break
- Real-time screening snapshots rebuilt after every sync
- Index symbols pre-seeded on first run (Nifty 50, Bank Nifty, Midcap, IT)

### Charting
- Candlestick, Heikin-Ashi, Renko, and Line Break charts
- Lightweight Charts v5 — fast, responsive, mobile-friendly
- Overlays: SMA 20 / 50 / 200, EMA, Bollinger Bands, Volume

### Data Sync
- Incremental historical data download from Yahoo Finance (3-year history by default)
- Bulk symbol import from NSE EQUITY_L_ACTIVE.csv
- Sync status dashboard with per-symbol error tracking

### Settings
- Database: switch between SQLite (default) and MSSQL / PostgreSQL without reinstalling
- AI: configure local Ollama or any OpenAI-compatible endpoint for analysis
- All settings persisted in the database — survive upgrades

### AI Analysis
- Trade plan generation per symbol
- Market regime detection
- Opportunity scanner across the full NSE universe

---

## Downloads

| Platform | File | Size |
|----------|------|------|
| Windows 10/11 (64-bit) | `VajraStocks-Setup.exe` | ~85 MB |
| Linux — Debian / Ubuntu | `VajraStocks.deb` | ~80 MB |
| Linux — Fedora / RHEL | `VajraStocks.rpm` | ~80 MB |
| Linux — Universal | `VajraStocks.AppImage` | ~82 MB |
| macOS 12+ | `VajraStocks.dmg` | ~80 MB |

Checksums: `Checksums.txt` (SHA-256)

---

## Installation

### Windows
1. Download `VajraStocks-Setup.exe`
2. Run the installer and follow the wizard
3. Launch via the Desktop shortcut or Start Menu

### Linux (.deb — Debian, Ubuntu, Mint)
```bash
sudo dpkg -i VajraStocks.deb
vajrastocks
```

### Linux (.rpm — Fedora, RHEL, openSUSE)
```bash
sudo rpm -i VajraStocks.rpm
vajrastocks
```

### Linux (AppImage — any distro)
```bash
chmod +x VajraStocks.AppImage
./VajraStocks.AppImage
```

### macOS
1. Open `VajraStocks.dmg`
2. Drag **VajraStocks** to the **Applications** folder
3. Right-click → Open on first launch (Gatekeeper warning on unsigned builds)

---

## System Requirements

| | Minimum | Recommended |
|---|---|---|
| OS | Windows 10 / Ubuntu 20.04 / macOS 12 | Windows 11 / Ubuntu 22.04+ / macOS 14 |
| RAM | 2 GB | 4 GB |
| Disk | 500 MB | 2 GB (for 3 years of price data) |
| Internet | Required for data sync | — |

---

## Known Limitations

- AI features require a locally running [Ollama](https://ollama.ai) instance or an OpenAI-compatible API endpoint configured in Settings
- MSSQL support on Linux/macOS requires `unixODBC` to be installed separately (`sudo apt install unixodbc`)
- macOS builds are not code-signed — Gatekeeper will show a warning on first launch; right-click → Open to proceed

---

## Upgrading

No automatic updater in v1.0.0. To upgrade:
1. Download the new installer
2. Run it over the existing installation — your database and settings are preserved
3. The old version is replaced automatically

---

## Feedback & Issues

[https://github.com/abhishek4official/VajraStocks/issues](https://github.com/abhishek4official/VajraStocks/issues)
