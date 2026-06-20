"""Settings CRUD API — read and update application settings stored in the database."""

import asyncio
import os
import sys

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session

from stocks.api.deps import get_db
from stocks.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["Settings"])

# ── Settings that require a full server restart to take effect ─────────────────
# Anything that is read once at startup (DB pool, log config, AI client init).
RESTART_REQUIRED_KEYS: set[tuple[str, str]] = {
    ("DATABASE", "db_connection_string"),
    ("DATABASE", "db_provider"),
    ("DATABASE", "db_pool_size"),
    ("DATABASE", "db_max_overflow"),
    ("DATABASE", "db_pool_recycle"),
    ("AI",       "ai_provider"),
    ("AI",       "ai_base_url"),
    ("AI",       "ai_model"),
    ("APPLICATION", "log_level_console"),
    ("APPLICATION", "log_level_file"),
    ("APPLICATION", "log_file_path"),
}


class SettingUpdate(BaseModel):
    value: str


@router.get("")
def get_all_settings(db: Session = Depends(get_db)):
    """Returns all settings grouped by category. Secret values are masked."""
    svc = SettingsService(db)
    return svc.settings_by_category()


@router.get("/restart-required-keys")
def get_restart_required_keys():
    """Returns the list of setting keys that require a server restart when changed."""
    return [{"category": cat, "key": key} for cat, key in sorted(RESTART_REQUIRED_KEYS)]


@router.put("/{category}/{key}")
def update_setting(category: str, key: str, body: SettingUpdate, db: Session = Depends(get_db)):
    """
    Updates a single setting value in the database.

    If the key is a bootstrap key (DATABASE/*, AI/* provider settings), also
    rewrites config.yaml so the next server restart uses the new value — even
    if the DB connection itself has changed.
    """
    from stocks.api.main import BOOTSTRAP_KEYS, write_bootstrap_config

    svc = SettingsService(db)

    all_flat = svc.all_settings()
    exists = any(s["category"] == category.upper() and s["key"] == key for s in all_flat)
    if not exists:
        raise HTTPException(status_code=404, detail=f"Setting '{category}/{key}' not found.")

    # Pre-flight connectivity check when changing the database connection string.
    if (category.upper(), key) == ("DATABASE", "db_connection_string"):
        try:
            from sqlalchemy import create_engine
            from sqlalchemy import text as _text
            _extra = {"check_same_thread": False} if body.value.lower().startswith("sqlite") else {}
            _test_engine = create_engine(body.value, connect_args=_extra)
            with _test_engine.connect() as _conn:
                _conn.execute(_text("SELECT 1"))
            _test_engine.dispose()
        except Exception as _exc:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot connect to the new database — please check the connection string. Error: {_exc}",
            )

    svc.set(category.upper(), key, body.value)

    needs_restart = (category.upper(), key) in RESTART_REQUIRED_KEYS

    # If this is a bootstrap key, persist it to config.yaml immediately so the
    # next restart can boot even if the DB connection string just changed.
    if (category.upper(), key) in BOOTSTRAP_KEYS:
        write_bootstrap_config({(category.upper(), key): body.value})

    return {
        "status": "updated",
        "category": category.upper(),
        "key": key,
        "restart_required": needs_restart,
        "config_yaml_updated": (category.upper(), key) in BOOTSTRAP_KEYS,
    }


@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    """Returns available categories with metadata (label, setting count, has restart-required keys)."""
    svc = SettingsService(db)
    by_cat = svc.settings_by_category()
    restart_cats = {cat for cat, _ in RESTART_REQUIRED_KEYS}
    labels = {
        "AI":          "AI Provider",
        "DATABASE":    "Database",
        "DOWNLOADER":  "Data Downloader",
        "MARKET":      "Market",
        "SCREENER":    "Screener Defaults",
        "PORTFOLIO":   "Portfolio",
        "UI":          "Interface",
        "APPLICATION": "Application",
    }
    order = ["AI", "DATABASE", "DOWNLOADER", "MARKET", "SCREENER", "PORTFOLIO", "UI", "APPLICATION"]
    result = []
    for cat in order:
        if cat in by_cat:
            result.append({
                "category": cat,
                "label": labels.get(cat, cat),
                "count": len(by_cat[cat]),
                "has_restart_required": cat in restart_cats,
            })
    # Append any unlisted categories
    for cat in by_cat:
        if cat not in order:
            result.append({
                "category": cat,
                "label": labels.get(cat, cat),
                "count": len(by_cat[cat]),
                "has_restart_required": cat in restart_cats,
            })
    return result


@router.post("/reset/{category}")
def reset_category(category: str, db: Session = Depends(get_db)):
    """Resets all settings in a category back to their seeded default values."""
    from stocks.api.main import BOOTSTRAP_KEYS, write_bootstrap_config
    from stocks.services.settings_service import DEFAULT_SETTINGS

    cat_upper = category.upper()
    defaults = [(k, v) for c, k, v, *_ in DEFAULT_SETTINGS if c == cat_upper]
    if not defaults:
        raise HTTPException(status_code=404, detail=f"Category '{category}' not found.")
    svc = SettingsService(db)
    bootstrap_updates: dict[tuple[str, str], str] = {}
    for key, value in defaults:
        svc.set(cat_upper, key, value)
        if (cat_upper, key) in BOOTSTRAP_KEYS:
            bootstrap_updates[(cat_upper, key)] = value
    if bootstrap_updates:
        write_bootstrap_config(bootstrap_updates)
    restart_needed = any((cat_upper, k) in RESTART_REQUIRED_KEYS for k, _ in defaults)
    return {
        "status": "reset",
        "category": cat_upper,
        "reset_count": len(defaults),
        "restart_required": restart_needed,
        "config_yaml_updated": bool(bootstrap_updates),
    }


@router.post("/reload")
def reload_settings(request: Request, db: Session = Depends(get_db)):
    """Busts the in-process settings cache so next read picks up DB values."""
    return {"status": "ok", "message": "Settings cache will refresh on next read."}


@router.post("/restart")
async def restart_server(request: Request):
    """
    Restarts the uvicorn server process (Windows-safe).

    Builds the exact uvicorn command from the current process arguments,
    sets the working directory to the project root (python/), then spawns a
    detached child before exiting the parent.  The frontend polls /health
    every 2 s until the new process responds.
    """
    import subprocess
    from pathlib import Path as _Path

    logger.warning("Server restart requested via Settings API.")

    # Reconstruct the uvicorn launch command reliably.
    # sys.argv[0] is uvicorn's __main__.py path when launched via `python -m uvicorn`.
    # We rebuild the command explicitly so the cwd / pythonpath are always correct.
    python_dir = _Path(__file__).resolve().parents[4]  # python/
    uvicorn_args = ["stocks.api.main:app"]

    # Preserve host / port from the current argv
    argv = sys.argv
    for flag in ("--host", "--port", "--reload"):
        try:
            idx = argv.index(flag)
            uvicorn_args += [flag, argv[idx + 1]]
        except (ValueError, IndexError):
            pass
    # Default host/port if not found
    if "--host" not in uvicorn_args:
        uvicorn_args += ["--host", "127.0.0.1"]
    if "--port" not in uvicorn_args:
        uvicorn_args += ["--port", "8000"]

    if getattr(sys, "frozen", False):
        # PyInstaller build: sys.executable is the packaged binary; it must be
        # launched directly without "-m uvicorn" arguments.
        cmd = [sys.executable]
    else:
        cmd = [sys.executable, "-m", "uvicorn"] + uvicorn_args

    async def _do_restart():
        await asyncio.sleep(0.5)
        logger.info(f"Restarting → {' '.join(cmd)}  (cwd={python_dir})")
        kwargs: dict = {"cwd": str(python_dir)}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen(cmd, **kwargs)
        await asyncio.sleep(0.8)
        logger.info("Parent exiting — new process is taking over.")
        os._exit(0)

    asyncio.create_task(_do_restart())

    return JSONResponse(
        status_code=200,
        content={"status": "restarting", "message": "Server is restarting. Reconnecting in a few seconds…"},
    )
