# VajraStocks — Windows Installer
# Run this once to set up the application on a new machine.
# Usage: Right-click → Run with PowerShell (as current user, no admin needed)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$AppDir   = $PSScriptRoot
$DataDir  = "$env:LOCALAPPDATA\VajraStocks"
$ShortcutPath = "$env:USERPROFILE\Desktop\VajraStocks.lnk"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   VajraStocks — Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check Python 3.12+
Write-Host "[1/5] Checking Python..." -ForegroundColor Yellow
try {
    $pyVer = python --version 2>&1
    if ($pyVer -match "Python 3\.(1[2-9]|[2-9]\d)") {
        Write-Host "      Python OK: $pyVer" -ForegroundColor Green
    } else {
        Write-Host "      Python 3.12+ required. Found: $pyVer" -ForegroundColor Red
        Write-Host "      Install from https://python.org/downloads or via winget:" -ForegroundColor Yellow
        Write-Host "      winget install Python.Python.3.12" -ForegroundColor White
        Read-Host "Press Enter to exit"
        exit 1
    }
} catch {
    Write-Host "      Python not found. Installing via winget..." -ForegroundColor Yellow
    winget install -e --id Python.Python.3.12 --silent
}

# 2. Install uv
Write-Host "[2/5] Installing uv package manager..." -ForegroundColor Yellow
try {
    $uvVer = uv --version 2>&1
    Write-Host "      uv OK: $uvVer" -ForegroundColor Green
} catch {
    pip install uv --quiet
    Write-Host "      uv installed." -ForegroundColor Green
}

# 3. Backend dependencies
Write-Host "[3/5] Installing backend dependencies..." -ForegroundColor Yellow
Set-Location $AppDir
uv sync --quiet
Write-Host "      Backend dependencies OK." -ForegroundColor Green

# 4. Frontend build
Write-Host "[4/5] Building frontend..." -ForegroundColor Yellow
Set-Location "$AppDir\frontend"
if (-not (Test-Path "node_modules")) {
    npm install --silent
}
npm run build --silent
Write-Host "      Frontend built." -ForegroundColor Green
Set-Location $AppDir

# 5. Create data directory
Write-Host "[5/5] Creating data directory and desktop shortcut..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "$AppDir\data" | Out-Null
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

# Create start.ps1 launcher
$startScript = @"
Set-Location '$AppDir'
Start-Process "http://localhost:8000" -ErrorAction SilentlyContinue
uv run uvicorn stocks.api.main:app --host 127.0.0.1 --port 8000
"@
$startScript | Out-File -FilePath "$AppDir\start.ps1" -Encoding utf8 -Force

# Create Desktop shortcut
$wsh = New-Object -ComObject WScript.Shell
$sc  = $wsh.CreateShortcut($ShortcutPath)
$sc.TargetPath       = "powershell.exe"
$sc.Arguments        = "-ExecutionPolicy Bypass -WindowStyle Minimized -File `"$AppDir\start.ps1`""
$sc.WorkingDirectory = $AppDir
$sc.Description      = "VajraStocks — NSE Analysis Platform"
$sc.IconLocation     = "powershell.exe"
$sc.Save()

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "   Installation complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "   A 'VajraStocks' shortcut has been added to your Desktop." -ForegroundColor White
Write-Host "   Double-click it to start the application." -ForegroundColor White
Write-Host "   The app opens in your browser at http://localhost:8000" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to exit"
