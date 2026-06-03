# VajraStocks — Launcher
# Opens the app in the default browser and starts the FastAPI server.

$AppDir = $PSScriptRoot
Set-Location $AppDir

# Open browser first (non-blocking)
Start-Process "http://localhost:8000" -ErrorAction SilentlyContinue

# Start the API server (blocking — keep this window open)
Write-Host "Starting VajraStocks on http://localhost:8000 ..." -ForegroundColor Cyan
Write-Host "Close this window to stop the server." -ForegroundColor Gray
uv run uvicorn stocks.api.main:app --host 127.0.0.1 --port 8000
