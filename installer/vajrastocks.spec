# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — bundles the FastAPI backend + pre-built frontend dist
# into a single-folder distribution (onedir mode for faster startup).
#
# Entry point is installer/launcher.py (NOT stocks/api/main.py).
#
# Run from repo root after building the frontend:
#   cd python && uv run pyinstaller ../installer/vajrastocks.spec

import sys
from pathlib import Path

ROOT        = Path(SPECPATH).parent
PYTHON_SRC  = ROOT / "python" / "src"
FRONTEND_DIST = ROOT / "frontend" / "dist"
PYTHON_CONFIG = ROOT / "python" / "config"
ICON_ICO    = ROOT / "installer" / "assets" / "icon.ico"

# ── Bundle unixODBC shared library on Linux / macOS ──────────────────────────
# pyodbc dynamically links against libodbc.so.2 (unixODBC).  PyInstaller's
# dependency walker sometimes misses system libraries.  Explicitly bundle it
# so the app doesn't crash with "libodbc.so.2: cannot open shared object file"
# on machines where unixODBC isn't installed.
extra_binaries = []
if sys.platform.startswith("linux"):
    import glob as _glob
    for pattern in [
        "/usr/lib/x86_64-linux-gnu/libodbc.so*",
        "/usr/lib/libodbc.so*",
        "/usr/local/lib/libodbc.so*",
    ]:
        hits = _glob.glob(pattern)
        if hits:
            extra_binaries += [(h, ".") for h in hits]
            break
elif sys.platform == "darwin":
    import glob as _glob
    for pattern in [
        "/usr/local/lib/libodbc*.dylib",
        "/opt/homebrew/lib/libodbc*.dylib",
    ]:
        hits = _glob.glob(pattern)
        if hits:
            extra_binaries += [(h, ".") for h in hits]
            break

a = Analysis(
    [str(ROOT / "installer" / "launcher.py")],
    pathex=[str(PYTHON_SRC)],
    binaries=extra_binaries,
    datas=[
        (str(FRONTEND_DIST),                          "frontend/dist"),
        # Use the installer-specific config.yaml (SQLite default) rather than
        # the dev config which points to MSSQL LocalDB.
        (str(ROOT / "installer" / "config.yaml"),     "config"),
        # Bundle EQUITY_L_ACTIVE.csv for offline symbol seeding
        (str(PYTHON_CONFIG / "EQUITY_L_ACTIVE.csv"),  "config"),
        (str(ROOT / "python" / "migrations"),         "migrations"),
        (str(ROOT / "python" / "alembic.ini"),        "."),
    ],
    hiddenimports=[
        # ── Application modules ───────────────────────────────────────────────
        "stocks",
        "stocks.api",
        "stocks.api.main",
        "stocks.api.v1.router",
        "stocks.api.v1.endpoints.actions",
        "stocks.api.v1.endpoints.agents",
        "stocks.api.v1.endpoints.charts",
        "stocks.api.v1.endpoints.indicators",
        "stocks.api.v1.endpoints.screening",
        "stocks.api.v1.endpoints.settings",
        "stocks.api.v1.endpoints.setup",
        "stocks.api.v1.endpoints.symbols",
        "stocks.api.v1.endpoints.sync",
        "stocks.config",
        "stocks.db.connection",
        "stocks.db.models",
        "stocks.db.repositories.price_repo",
        "stocks.main",
        "stocks.services.database",
        "stocks.services.downloader",
        "stocks.services.indicator_engine",
        "stocks.services.market_structure",
        "stocks.services.screening",
        "stocks.services.settings_service",
        "stocks.services.symbol",
        "stocks.services.sync_engine",
        "stocks.services.validation",
        "stocks.services.agents.llm_client",
        "stocks.services.agents.orchestrator",
        "stocks.services.quant.backtester",
        "stocks.services.quant.planner",
        "stocks.utils.exceptions",
        "stocks.utils.logging",
        "stocks.utils.telemetry",
        # ── uvicorn internals (not auto-detected) ─────────────────────────────
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        # ── FastAPI / Starlette (static files + responses used in main.py) ────
        "fastapi.staticfiles",
        "fastapi.responses",
        "starlette.staticfiles",
        "starlette.responses",
        # ── SQLAlchemy dialects — SQLite (default) + MSSQL (optional) ─────────
        "sqlalchemy.dialects.sqlite",
        "sqlalchemy.dialects.mssql",
        "sqlalchemy.dialects.mssql.pyodbc",
        "sqlalchemy.pool",
        # ── Alembic ───────────────────────────────────────────────────────────
        "alembic.runtime.migration",
        "alembic.operations",
        "alembic.operations.ops",
        # ── Data / ML libraries ───────────────────────────────────────────────
        "pandas_ta",
        "aiosqlite",
        # ── ODBC ─────────────────────────────────────────────────────────────
        "pyodbc",
    ],
    excludes=["tkinter", "test", "unittest", "_pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VajraStocks",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX is disabled — it is known to corrupt numpy/pandas compiled extensions
    # and cause silent runtime crashes even when the build succeeds.
    upx=False,
    console=True,   # keep console window so errors are visible; set False once stable
    icon=str(ICON_ICO) if ICON_ICO.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="VajraStocks",
)
