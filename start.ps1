# VajraStocks - Launcher
$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $AppDir
Start-Process "http://localhost:8000" -ErrorAction SilentlyContinue
Write-Host "Starting VajraStocks on http://localhost:8000 ..." -ForegroundColor Cyan
Write-Host "Close this window to stop the server." -ForegroundColor Gray
uv run uvicorn stocks.api.main:app --host 127.0.0.1 --port 8000