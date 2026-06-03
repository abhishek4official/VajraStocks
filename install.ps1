# VajraStocks - Windows Installer
# Usage: powershell -ExecutionPolicy Bypass -File .\install.ps1

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ShortcutPath = "$env:USERPROFILE\Desktop\VajraStocks.lnk"

Write-Host ""
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "   VajraStocks - Setup" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check uv
Write-Host "[1/4] Checking uv package manager..." -ForegroundColor Yellow
$uvOk = $false
try { $ver = (uv --version) 2>$null; if ($ver) { $uvOk = $true } } catch { }
if (-not $uvOk) {
    Write-Host "      Installing uv via pip..." -ForegroundColor Yellow
    pip install uv
} else {
    Write-Host "      uv OK: $ver" -ForegroundColor Green
}

# 2. Backend dependencies
Write-Host "[2/4] Installing backend dependencies..." -ForegroundColor Yellow
Set-Location $AppDir
uv sync 2>$null
Write-Host "      Backend OK." -ForegroundColor Green

# 3. Frontend build
Write-Host "[3/4] Building frontend..." -ForegroundColor Yellow
Set-Location (Join-Path $AppDir "frontend")
if (-not (Test-Path "node_modules")) { npm install }
npm run build
Set-Location $AppDir
Write-Host "      Frontend OK." -ForegroundColor Green

# 4. Shortcut
Write-Host "[4/4] Creating Desktop shortcut..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path (Join-Path $AppDir "data") | Out-Null
$wsh = New-Object -ComObject WScript.Shell
$sc = $wsh.CreateShortcut($ShortcutPath)
$sc.TargetPath = "powershell.exe"
$sc.Arguments = "-ExecutionPolicy Bypass -WindowStyle Normal -File " + (Join-Path $AppDir "start.ps1")
$sc.WorkingDirectory = $AppDir
$sc.Description = "VajraStocks NSE Analysis Platform"
$sc.Save()
Write-Host "      Shortcut created on Desktop." -ForegroundColor Green

Write-Host ""
Write-Host "=======================================" -ForegroundColor Green
Write-Host "   Setup complete!" -ForegroundColor Green
Write-Host "   Double-click VajraStocks on your" -ForegroundColor Green
Write-Host "   Desktop to launch the app." -ForegroundColor Green
Write-Host "   Opens at http://localhost:8000" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Green
Write-Host ""