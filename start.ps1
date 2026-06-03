# VajraStocks - Launcher
# Forces use of THIS project's own venv to avoid loading stale code from another venv.

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $AppDir

$VenvPython = Join-Path $AppDir ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Project venv not found. Run install.ps1 first." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Start-Process "http://localhost:8000" -ErrorAction SilentlyContinue

Write-Host "Starting VajraStocks on http://localhost:8000 ..." -ForegroundColor Cyan
Write-Host "Using venv: $VenvPython" -ForegroundColor Gray
Write-Host "Close this window to stop the server." -ForegroundColor Gray

& $VenvPython -m uvicorn stocks.api.main:app --host 127.0.0.1 --port 8000
