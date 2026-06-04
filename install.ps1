# VajraStocks - Windows Installer
# Usage: powershell -ExecutionPolicy Bypass -File .\install.ps1

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PyDir   = Join-Path $RootDir "python"
$FeDir   = Join-Path $RootDir "frontend"
$ShortcutPath = "$env:USERPROFILE\Desktop\VajraStocks.lnk"

Write-Host ""
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "   VajraStocks - Setup" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

# 1. uv
Write-Host "[1/4] Checking uv package manager..." -ForegroundColor Yellow
$uvOk = $false
try { $ver = (uv --version) 2>$null; if ($ver) { $uvOk = $true } } catch { }
if (-not $uvOk) { Write-Host "      Installing uv via pip..." -ForegroundColor Yellow; pip install uv }
else { Write-Host "      uv OK: $ver" -ForegroundColor Green }

# 2. Backend deps (in python/)
Write-Host "[2/4] Installing backend dependencies..." -ForegroundColor Yellow
Set-Location $PyDir
uv sync 2>$null
Write-Host "      Backend OK." -ForegroundColor Green

# 3. Frontend build (in frontend/)
Write-Host "[3/4] Building frontend..." -ForegroundColor Yellow
Set-Location $FeDir
if (-not (Test-Path "node_modules")) { npm install }
npm run build
Set-Location $RootDir
Write-Host "      Frontend OK." -ForegroundColor Green

# 4. Shortcut
Write-Host "[4/4] Creating Desktop shortcut..." -ForegroundColor Yellow
$wsh = New-Object -ComObject WScript.Shell
$sc = $wsh.CreateShortcut($ShortcutPath)
$sc.TargetPath = "powershell.exe"
$sc.Arguments = "-ExecutionPolicy Bypass -WindowStyle Normal -File " + (Join-Path $RootDir "start.ps1")
$sc.WorkingDirectory = $RootDir
$sc.Description = "VajraStocks NSE Analysis Platform"
$sc.Save()
Write-Host "      Shortcut created on Desktop." -ForegroundColor Green

Write-Host ""
Write-Host "=======================================" -ForegroundColor Green
Write-Host "   Setup complete! Launch via the" -ForegroundColor Green
Write-Host "   VajraStocks Desktop shortcut." -ForegroundColor Green
Write-Host "   Opens at http://localhost:8000" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Green
Write-Host ""