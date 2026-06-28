# ─────────────────────────────────────────────────────────────────────────────
# build_electron.ps1 — Full VajraStocks Electron installer build
#
# Steps:
#   1. Build React frontend  (npm run build  in frontend/)
#   2. Bundle Python backend (pyinstaller    in python/)
#   3. Package Electron app  (electron-builder in electron/)
#
# Output: release/VajraStocks-Setup.exe
#
# Requirements (must be on PATH):
#   node / npm, python / uv, pyinstaller (via uv run)
# ─────────────────────────────────────────────────────────────────────────────

param(
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

# ── Resolve version ───────────────────────────────────────────────────────────
if (-not $Version) {
    $pkg = Get-Content "$Root\frontend\package.json" | ConvertFrom-Json
    $Version = $pkg.version
}
Write-Host "`n=== VajraStocks Electron build v$Version ===" -ForegroundColor Cyan

# ── 1. Frontend ───────────────────────────────────────────────────────────────
Write-Host "`n[1/3] Building frontend..." -ForegroundColor Yellow
Set-Location "$Root\frontend"
npm ci --prefer-offline
npm run build
Write-Host "      Frontend built -> frontend/dist/" -ForegroundColor Green

# ── 2. Python backend (PyInstaller) ──────────────────────────────────────────
Write-Host "`n[2/3] Bundling Python backend..." -ForegroundColor Yellow
Set-Location "$Root\python"
uv run pyinstaller ../installer/vajrastocks.spec --noconfirm
Write-Host "      Backend bundled -> dist/VajraStocks/" -ForegroundColor Green

# ── 3. Electron installer ─────────────────────────────────────────────────────
Write-Host "`n[3/3] Building Electron installer..." -ForegroundColor Yellow
Set-Location "$Root\electron"

# Install electron deps if node_modules missing
if (-not (Test-Path "node_modules")) {
    npm install
}

# Inject version into electron package.json
$ePkg = Get-Content "package.json" | ConvertFrom-Json
$ePkg.version = $Version
$ePkg | ConvertTo-Json -Depth 10 | Set-Content "package.json" -Encoding utf8

$env:APP_VERSION = $Version
npm run build:win

Write-Host "`n=== Done! ===" -ForegroundColor Cyan
Write-Host "Installer: $Root\release\VajraStocks-Setup.exe" -ForegroundColor Green

Set-Location $Root
