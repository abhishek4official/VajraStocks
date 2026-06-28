"""FastAPI application entry point with lifespan-managed database and settings bootstrap."""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from loguru import logger


# ── config.yaml location ─────────────────────────────────────────────────────

def _get_user_appdata_dir() -> Path | None:
    """Returns the platform-appropriate per-user data directory for VajraStocks."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        return Path(appdata) / "VajraStocks" if appdata else None
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "VajraStocks"
    # Linux / BSD — respect XDG_DATA_HOME
    xdg = os.environ.get("XDG_DATA_HOME", "")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "VajraStocks"


def _resolve_config_yaml() -> Path:
    # 1. Explicit env var — always wins (set by frozen launcher or Docker).
    env = os.environ.get("VAJRA_CONFIG_YAML")
    if env:
        return Path(env)
    # 2. Platform-appropriate per-user directory (installed build).
    user_dir = _get_user_appdata_dir()
    if user_dir:
        user_cfg = user_dir / "config.yaml"
        if user_cfg.exists():
            return user_cfg
    # 3. Source-tree fallback for dev mode.
    # python/src/stocks/api/main.py → parents[3] = python/
    return Path(__file__).resolve().parents[3] / "config" / "config.yaml"

_CONFIG_YAML = _resolve_config_yaml()

# Bootstrap keys that must survive in config.yaml so the app can always restart.
# When any of these is changed via the Settings UI, config.yaml is rewritten.
BOOTSTRAP_KEYS: set[tuple[str, str]] = {
    ("DATABASE", "db_connection_string"),
    ("DATABASE", "db_provider"),
    ("DATABASE", "db_pool_size"),
    ("DATABASE", "db_max_overflow"),
    ("DATABASE", "db_pool_recycle"),
    ("AI",       "ai_provider"),
    ("AI",       "ai_base_url"),
    ("AI",       "ai_model"),
}


# ── Startup helpers ───────────────────────────────────────────────────────────

def _load_connection_string() -> str:
    """
    Resolves the DB connection string with this priority:
      1. VAJRA_DB_URL  environment variable  (Docker / CI override)
      2. config.yaml   database.connection_string  ← primary source
         Checked first at %APPDATA%\\VajraStocks\\config.yaml (installed build),
         then at python/config/config.yaml (dev fallback).
      3. SQLite default for a completely fresh install with no config yet.

    No silent DB fallback — if initialize() fails the error propagates and the
    server refuses to start with a clear log message.
    """
    # 1. Hard env-var override
    env_cs = os.getenv("VAJRA_DB_URL")
    if env_cs:
        logger.debug("Connection string from VAJRA_DB_URL env var.")
        return env_cs

    # 2. config.yaml
    if _CONFIG_YAML.exists():
        try:
            with open(_CONFIG_YAML, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            cs = data.get("database", {}).get("connection_string", "")
            if cs:
                logger.debug(f"Connection string from config.yaml: {cs[:60]}…")
                return cs
        except Exception as exc:
            logger.warning(f"Could not read config.yaml: {exc}")

    # 3. Default SQLite
    logger.debug("Using default SQLite connection string.")
    return "sqlite:///data/vajra.db"


def write_bootstrap_config(updates: dict[tuple[str, str], str]) -> None:
    """
    Rewrites config.yaml with updated bootstrap values.

    ``updates`` is a dict of  (CATEGORY, key) → new_value  for the keys that
    changed.  All other existing values in config.yaml are preserved.
    Called by the Settings PUT endpoint whenever a BOOTSTRAP_KEY is saved.
    """
    # Load existing file or start from empty dict
    existing: dict = {}
    if _CONFIG_YAML.exists():
        try:
            with open(_CONFIG_YAML, encoding="utf-8") as f:
                existing = yaml.safe_load(f) or {}
        except Exception as exc:
            logger.warning(f"write_bootstrap_config: could not read existing config.yaml: {exc}")

    # Map (CATEGORY, key) → config.yaml path
    KEY_MAP: dict[tuple[str, str], tuple[str, str]] = {
        ("DATABASE", "db_connection_string"): ("database", "connection_string"),
        ("DATABASE", "db_provider"):          ("database", "provider"),
        ("DATABASE", "db_pool_size"):         ("database", "pool_size"),
        ("DATABASE", "db_max_overflow"):      ("database", "max_overflow"),
        ("DATABASE", "db_pool_recycle"):      ("database", "pool_recycle"),
        ("AI",       "ai_provider"):          ("ai", "provider"),
        ("AI",       "ai_base_url"):          ("ai", "base_url"),
        ("AI",       "ai_model"):             ("ai", "model"),
    }

    for (category, key), new_val in updates.items():
        mapping = KEY_MAP.get((category, key))
        if not mapping:
            continue
        section, field = mapping
        if section not in existing:
            existing[section] = {}
        # Cast to correct Python type so yaml dumps cleanly
        typed: object = new_val
        try:
            if key in ("db_pool_size", "db_max_overflow", "db_pool_recycle"):
                typed = int(new_val)
        except (ValueError, TypeError):
            pass
        existing[section][field] = typed

    try:
        _CONFIG_YAML.parent.mkdir(parents=True, exist_ok=True)
        with open(_CONFIG_YAML, "w", encoding="utf-8") as f:
            yaml.dump(existing, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        logger.info(f"config.yaml updated with bootstrap settings → {_CONFIG_YAML}")
    except Exception as exc:
        logger.error(f"write_bootstrap_config: failed to write config.yaml: {exc}")


def _seed_default_symbols(db_manager) -> None:
    """
    Seeds the minimum set of symbols the app needs to function on a fresh install:
      • NSE index symbols  (^NSEI, ^NSEBANK, ^CNXMIDCAP, ^NSMIDCP, ^CNXIT)
      • NSE equity symbols from the bundled EQUITY_L_ACTIVE.csv
        (only rows not already present — idempotent)

    This runs on every startup; already-present symbols are never touched.
    """
    from pathlib import Path as _Path
    from stocks.db.models import Symbol
    from sqlalchemy import select

    session = db_manager.get_session()
    try:
        # ── 1. Index symbols ────────────────────────────────────────────────────
        INDEX_SYMBOLS: dict[str, str] = {
            "^NSEI":    "Nifty 50 Index",
            "^NSEBANK": "Nifty Bank Index",
            "^CNXMIDCAP": "Nifty Midcap 100 Index",
            "^NSMIDCP": "Nifty Midcap 50 Index",
            "^CNXIT":   "Nifty IT Index",
        }
        idx_inserted = 0
        for ticker, name in INDEX_SYMBOLS.items():
            existing = session.scalar(select(Symbol).where(Symbol.symbol == ticker))
            if existing:
                if not existing.is_active:
                    existing.is_active = True
                    session.commit()
                continue
            session.add(Symbol(
                symbol=ticker,
                company_name=name,
                isin=f"IDX-{ticker.lstrip('^')}",
                series="INDEX",
                is_active=True,
            ))
            idx_inserted += 1

        if idx_inserted:
            session.commit()
            logger.info(f"Symbol seed: {idx_inserted} index symbol(s) inserted (^NSEI etc.).")
        else:
            logger.debug("Symbol seed: all index symbols already present.")

        # ── 2. Equity symbols from bundled CSV ──────────────────────────────────
        csv_candidates = [
            _Path(__file__).resolve().parents[4] / "config" / "EQUITY_L_ACTIVE.csv",  # python/config/
            _Path(__file__).resolve().parents[4] / "data"   / "EQUITY_L_ACTIVE.csv",
            _Path.cwd() / "config" / "EQUITY_L_ACTIVE.csv",
            _Path.cwd().parent / "config" / "EQUITY_L_ACTIVE.csv",
        ]
        csv_path = next((p for p in csv_candidates if p.exists()), None)

        if not csv_path:
            logger.debug("Symbol seed: EQUITY_L_ACTIVE.csv not found — skipping equity seed.")
            return

        lines = csv_path.read_text(encoding="utf-8").splitlines()
        if len(lines) < 2:
            return

        headers = [h.strip() for h in lines[0].split(",")]
        try:
            sym_idx  = headers.index("SYMBOL")
            name_idx = headers.index("NAME OF COMPANY")
            ser_idx  = headers.index("SERIES")
            isin_idx = headers.index("ISIN NUMBER")
        except ValueError:
            logger.warning("Symbol seed: CSV header format unrecognised — skipping equity seed.")
            return

        # Load existing tickers once → O(1) lookup
        existing_tickers: set[str] = set(
            session.scalars(select(Symbol.symbol)).all()
        )

        eq_inserted = 0
        batch: list[Symbol] = []
        for line in lines[1:]:
            if not line.strip():
                continue
            cols = line.split(",")
            max_idx = max(sym_idx, name_idx, ser_idx, isin_idx)
            if len(cols) <= max_idx:
                continue
            raw    = cols[sym_idx].strip()
            name   = cols[name_idx].strip()
            series = cols[ser_idx].strip()
            isin   = cols[isin_idx].strip()
            if not raw or not name or not isin:
                continue
            ticker = f"{raw}.NS"
            if ticker in existing_tickers:
                continue
            batch.append(Symbol(
                symbol=ticker,
                company_name=name,
                isin=isin,
                series=series,
                is_active=True,
            ))
            existing_tickers.add(ticker)
            eq_inserted += 1

        if batch:
            session.add_all(batch)
            session.commit()
            logger.info(f"Symbol seed: {eq_inserted} equity symbol(s) inserted from CSV.")
        else:
            logger.debug(f"Symbol seed: all {len(existing_tickers)} equity symbols already present.")

    except Exception as exc:
        session.rollback()
        logger.warning(f"Symbol seed skipped: {exc}")
    finally:
        session.close()


def _run_pending_migrations(connection_string: str) -> None:
    """Runs `alembic upgrade head` programmatically so the schema is always current.

    Pre-Alembic DBs (tables exist but no alembic_version row) are stamped with
    the current head so future startups skip migrations cleanly.
    """
    try:
        from alembic import command
        from alembic.config import Config as AlembicConfig
        from sqlalchemy import create_engine, inspect, text

        env_ini = os.environ.get("VAJRA_ALEMBIC_INI")
        if env_ini:
            alembic_ini = Path(env_ini)
        else:
            alembic_ini = Path(__file__).resolve().parents[3] / "alembic.ini"

        if not alembic_ini.exists():
            logger.warning(f"alembic.ini not found at {alembic_ini} — skipping migrations.")
            return

        alembic_cfg = AlembicConfig(str(alembic_ini))
        alembic_cfg.set_main_option("sqlalchemy.url", connection_string)

        # Detect a pre-Alembic DB: core tables exist but alembic_version doesn't.
        # Stamping tells Alembic "this DB is already at head" so it won't try to
        # re-run the initial CREATE TABLE migrations.
        _engine = create_engine(connection_string, connect_args={"check_same_thread": False})
        try:
            _insp = inspect(_engine)
            has_symbols = _insp.has_table("symbols")
            has_version = _insp.has_table("alembic_version")
            if has_symbols and not has_version:
                logger.info("Pre-Alembic DB detected (tables exist, no alembic_version). Stamping with head.")
                command.stamp(alembic_cfg, "head")
                logger.info("DB stamped at head — future startups will run incremental migrations only.")
                return
        finally:
            _engine.dispose()

        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations applied (alembic upgrade head).")
    except Exception as exc:
        logger.warning(f"Migration step skipped: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Ordered startup sequence — runs every time the server starts:

      ① Resolve connection string (env var → SQLite default)
      ② Connect DatabaseManager / create engine
      ③ EnsureCreated  — create any tables missing from the schema
      ④ Alembic upgrade head — apply pending migrations
      ⑤ seed_defaults()  — INSERT OR IGNORE all default settings rows
                            (picks up new rows added in new code versions)
      ⑥ ensure_default_symbols() — seed index symbols (^NSEI, ^NSEBANK…)
                                    so charts / RS score work on first run
      ⑦ Expose db_manager on app.state for request handlers
    """
    from stocks.db.connection import DatabaseManager
    from stocks.services.settings_service import SettingsService

    connection_string = _load_connection_string()
    logger.info(f"Starting VajraStocks [db: {connection_string.split('?')[0]}]")

    # ① + ② — connect; raise immediately on failure so the error is visible
    db_manager = DatabaseManager(connection_string)
    db_manager.initialize()

    # ③ — create any missing tables (idempotent)
    try:
        db_manager.create_tables_directly()
        logger.debug("Schema check complete (EnsureCreated).")
    except Exception as exc:
        logger.warning(f"EnsureCreated skipped: {exc}")

    # ③b — patch in columns missing from EXISTING tables (create_all never ALTERs)
    try:
        db_manager.ensure_columns()
    except Exception as exc:
        logger.warning(f"ensure_columns skipped: {exc}")

    # ④ — migrations
    _run_pending_migrations(connection_string)

    # ⑤ — seed settings defaults (always; INSERT OR IGNORE so it's idempotent)
    session = db_manager.get_session()
    try:
        svc = SettingsService(session)
        inserted = svc.seed_defaults()
        if inserted:
            logger.info(f"Settings seed: {inserted} new default(s) inserted.")
        else:
            logger.debug("Settings seed: all defaults already present.")
    except Exception as exc:
        logger.warning(f"Settings seed skipped: {exc}")
    finally:
        session.close()

    # ⑥ — seed default index symbols (idempotent — skips already-present ones)
    _seed_default_symbols(db_manager)

    # ⑦ — expose to request handlers
    app.state.db_manager = db_manager

    # ⑦c — background job worker (DB-backed queue; long work off the request thread)
    try:
        from stocks.services.jobs import handlers as _job_handlers  # noqa: F401 — registers handlers
        from stocks.services.jobs.worker import JobWorker
        app.state.job_worker = JobWorker(db_manager)
        app.state.job_worker.start()
    except Exception as exc:
        logger.warning(f"Job worker not started: {exc}")

    logger.info("Application startup complete.")

    # ⑧ — start background daily scheduler (00:00 UTC / 5:30 AM IST sync & missed runs check)
    import asyncio
    from stocks.services.scheduler import run_scheduler
    scheduler_task = asyncio.create_task(run_scheduler(db_manager))

    yield

    # Clean up: stop the job worker, wait for any in-flight sync, then cancel the loop
    try:
        if getattr(app.state, "job_worker", None):
            app.state.job_worker.stop()
    except Exception as exc:
        logger.warning(f"Job worker stop error: {exc}")
    from stocks.services.scheduler import shutdown_scheduler
    await shutdown_scheduler()
    logger.info("Stopping background scheduler task...")
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass

    db_manager.dispose()
    logger.info("Application shutdown complete.")


# ── App factory ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="VajraStocks — NSE Quantitative Analysis Platform",
    description="Local-first stock analysis, screening, portfolio tracking, and AI-powered research.",
    version="1.5.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",   # alternate dev port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.get("/health")
def health_check():
    """API liveness probe."""
    return {"status": "HEALTHY", "version": "1.5.0"}


# ── Routes ─────────────────────────────────────────────────────────────────────
from stocks.api.v1.router import api_router  # noqa: E402

app.include_router(api_router)

# ── Serve Vite frontend build ──────────────────────────────────────────────────
def _find_frontend_dist() -> Path | None:
    here = Path(__file__).resolve()
    candidates = [
        here.parent.parent.parent.parent.parent / "frontend" / "dist",
        here.parent.parent.parent.parent / "frontend" / "dist",
        Path.cwd() / "frontend" / "dist",
        Path.cwd().parent / "frontend" / "dist",
    ]
    for p in candidates:
        if (p / "index.html").exists():
            return p
    return None


_frontend_dist = _find_frontend_dist()
if _frontend_dist:
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    _assets_dir = _frontend_dist / "assets"
    if _assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        candidate = _frontend_dist / full_path
        if candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(_frontend_dist / "index.html"))

    logger.info(f"Serving frontend from: {_frontend_dist}")
else:
    logger.warning("frontend/dist not found — run 'npm run build' in the frontend directory")
