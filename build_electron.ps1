# ─────────────────────────────────────────────────────────────────────────────
# build_electron.ps1 — Full VajraStocks Electron installer build
#
# Steps:
#   1. Build React frontend  (npm run build  in frontend/)
#   2. Bundle Python backend (pyinstaller from python/.venv)
#   3. Package Electron app  (electron-builder in electron/)
#
# Output: release/VajraStocks-Setup.exe
# ─────────────────────────────────────────────────────────────────────────────

param(
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

function Invoke-Native {
    param([string]$Description, [scriptblock]$Command)
    Write-Host "      > $Description" -ForegroundColor Gray
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "FAILED: $Description (exit code $LASTEXITCODE)"
    }
}

# ── Resolve version ───────────────────────────────────────────────────────────
if (-not $Version) {
    $pkg = Get-Content "$Root\frontend\package.json" -Raw | ConvertFrom-Json
    $Version = $pkg.version
}
Write-Host "`n=== VajraStocks Electron build v$Version ===" -ForegroundColor Cyan

# ── 1. Frontend ───────────────────────────────────────────────────────────────
Write-Host "`n[1/3] Building frontend..." -ForegroundColor Yellow
Set-Location "$Root\frontend"
Invoke-Native "npm ci"       { npm ci --prefer-offline }
Invoke-Native "vite build"   { npm run build }
Write-Host "      Frontend built -> frontend/dist/" -ForegroundColor Green

# ── 2. Python backend (PyInstaller) ──────────────────────────────────────────
Write-Host "`n[2/3] Bundling Python backend..." -ForegroundColor Yellow
Set-Location "$Root\python"

# pyinstaller is installed as a uv tool (uv tool install pyinstaller).
# `uv tool run` works without needing the uv bin dir on PATH.
Invoke-Native "pyinstaller" { uv tool run pyinstaller ..\installer\vajrastocks.spec --noconfirm }
Write-Host "      Backend bundled -> dist/VajraStocks/" -ForegroundColor Green

# ── 3. Electron installer ─────────────────────────────────────────────────────
Write-Host "`n[3/3] Building Electron installer..." -ForegroundColor Yellow
Set-Location "$Root\electron"

if (-not (Test-Path "node_modules")) {
    Invoke-Native "npm install" { npm install }
}

# Stamp the version into electron/package.json using UTF-8 WITHOUT BOM.
# PowerShell 5.1's Set-Content -Encoding utf8 writes a BOM that breaks
# app-builder.exe's JSON parser.
$ePkgPath = "$Root\electron\package.json"
$ePkg = Get-Content $ePkgPath -Raw | ConvertFrom-Json
$ePkg.version = $Version
$json = $ePkg | ConvertTo-Json -Depth 10
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($ePkgPath, $json, $utf8NoBom)

$env:APP_VERSION = $Version
Invoke-Native "electron-builder" { npm run build:win }

Write-Host "`n=== Done! ===" -ForegroundColor Cyan
Write-Host "Installer: $Root\release\VajraStocks-Setup.exe" -ForegroundColor Green

Set-Location $Root
