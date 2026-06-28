# ─────────────────────────────────────────────────────────────────────────────
# build_electron.ps1 — Full VajraStocks Electron installer build
#
# Steps:
#   1. Build React frontend  (npm run build  in frontend/)
#   2. Bundle Python backend (pyinstaller uv tool)
#   3. Package Electron app  (electron-builder → %TEMP%, then copy installer here)
#
# Output: release\VajraStocks-Setup-<version>.exe
# ─────────────────────────────────────────────────────────────────────────────

param([string]$Version = "")

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

function Invoke-Native {
    param([string]$Desc, [scriptblock]$Cmd)
    Write-Host "      > $Desc" -ForegroundColor Gray
    & $Cmd
    if ($LASTEXITCODE -ne 0) { throw "FAILED: $Desc (exit code $LASTEXITCODE)" }
}

# ── Resolve version ───────────────────────────────────────────────────────────
if (-not $Version) {
    $Version = (Get-Content "$Root\frontend\package.json" -Raw | ConvertFrom-Json).version
}
Write-Host "`n=== VajraStocks Electron build v$Version ===" -ForegroundColor Cyan

# ── 1. Frontend ───────────────────────────────────────────────────────────────
Write-Host "`n[1/3] Building frontend..." -ForegroundColor Yellow
Set-Location "$Root\frontend"
Invoke-Native "npm ci"     { npm ci --prefer-offline }
Invoke-Native "vite build" { npm run build }
Write-Host "      Frontend built -> frontend/dist/" -ForegroundColor Green

# ── 2. Python backend (PyInstaller) ──────────────────────────────────────────
Write-Host "`n[2/3] Bundling Python backend..." -ForegroundColor Yellow
Set-Location "$Root\python"
Invoke-Native "pyinstaller" { uv tool run pyinstaller ..\installer\vajrastocks.spec --noconfirm }
Write-Host "      Backend bundled -> python/dist/VajraStocks/" -ForegroundColor Green

# ── 3. Electron installer ─────────────────────────────────────────────────────
Write-Host "`n[3/3] Building Electron installer..." -ForegroundColor Yellow
Set-Location "$Root\electron"

if (-not (Test-Path "node_modules")) {
    Invoke-Native "npm install" { npm install }
}

# Build into %TEMP% to avoid Claude / VS Code file-watcher locks on the
# workspace. The watcher grabs app.asar the moment it appears inside the
# project directory and prevents electron-builder from overwriting it.
$BuildTemp = "$env:TEMP\vajrastocks-electron-build"
if (Test-Path $BuildTemp) { Remove-Item $BuildTemp -Recurse -Force -ErrorAction SilentlyContinue }
New-Item -ItemType Directory -Path $BuildTemp -Force | Out-Null

# Stamp version + temp output dir into package.json (UTF-8 no-BOM).
$ePkgPath = "$Root\electron\package.json"
$ePkg = Get-Content $ePkgPath -Raw | ConvertFrom-Json
$ePkg.version = $Version
$ePkg.build.directories.output = $BuildTemp
$json = $ePkg | ConvertTo-Json -Depth 10
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($ePkgPath, $json, $utf8NoBom)

$env:APP_VERSION = $Version
Invoke-Native "electron-builder" { npm run build:win }

# Restore placeholder in package.json so it doesn't commit with a temp path.
$ePkg2 = Get-Content $ePkgPath -Raw | ConvertFrom-Json
$ePkg2.build.directories.output = "ELECTRON_OUTPUT_DIR_PLACEHOLDER"
$json2 = $ePkg2 | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText($ePkgPath, $json2, $utf8NoBom)

# Copy the installer (*.exe) from temp back into release/
$ReleaseDir = "$Root\release"
New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null
$installer = Get-ChildItem "$BuildTemp" -Filter "*.exe" -Recurse | Select-Object -First 1
if (-not $installer) { throw "No installer .exe found in $BuildTemp" }
$dest = "$ReleaseDir\$($installer.Name)"
Copy-Item $installer.FullName -Destination $dest -Force
Write-Host "      Installer copied -> release\$($installer.Name)" -ForegroundColor Green

Write-Host "`n=== Done! ===" -ForegroundColor Cyan
Write-Host "Installer: $dest" -ForegroundColor Green

Set-Location $Root
