"""FastAPI application entry point with lifespan-managed database and settings bootstrap."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from loguru import logger


def _detect_first_run(connection_string: str) -> bool:
    """Returns True if this appears to be a first-run (no DB or empty settings table)."""
    import re

    cs = connection_string.lower()
    if cs.startswith("sqlite"):
        # Extract file path from sqlite:///path/to/file.db
        path_str = re.sub(r"^sqlite:///", "", connection_string.split("?")[0])
        if not path_str or path_str == ":memory:":
            return False
        db_path = Path(path_str)
        if not db_path.is_absolute():
            db_path = Path.cwd() / db_path
        return not db_path.exists()
    # For MSSQL/PostgreSQL we can't easily detect first-run without connecting
    # Fall through — bootstrap will handle an empty settings table gracefully
    return False


def _load_initial_connection_string() -> str:
    """Reads the connection string: env var → config.yaml → SQLite default."""
    import os

    # 1. Environment variable override (useful for Docker / CI)
    env_cs = os.getenv("VAJRA_DB_URL")
    if env_cs:
        return env_cs

    # 2. config.yaml (legacy path — still respected for existing users)
    from stocks.config import Config
    try:
        cfg = Config.load()
        return cfg.database.connection_string
    except Exception:
        pass

    # 3. Default: SQLite in local data/ directory
    return "sqlite:///data/vajra.db"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialise DB + settings, run migrations, serve app."""
    from stocks.db.connection import DatabaseManager
    from stocks.db.models import AppSetting
    from stocks.services.settings_service import SettingsService
    from sqlalchemy import select

    connection_string = _load_initial_connection_string()
    first_run = _detect_first_run(connection_string)

    logger.info(f"Starting VajraStocks [provider: {connection_string.split(':')[0]}, first_run: {first_run}]")

    # Initialise DB
    db_manager = DatabaseManager(connection_string)
    db_manager.initialize()

    # Ensure all tables exist (idempotent — create_all only creates missing tables).
    # This covers: fresh SQLite installs AND existing MSSQL DBs missing the new app_settings table.
    try:
        db_manager.create_tables_directly()
    except Exception as e:
        logger.warning(f"Table creation check skipped: {e}")

    # Seed settings if table is empty
    session = db_manager.get_session()
    try:
        settings_count = session.scalar(select(AppSetting).limit(1))
        if settings_count is None:
            logger.info("Seeding default application settings...")
            svc = SettingsService(session)
            svc.seed_defaults()

            # Import existing config.yaml values if present
            from stocks.config import Config
            config_path = Path("config/config.yaml")
            if config_path.exists():
                logger.info("Importing existing config.yaml values into settings DB...")
                try:
                    cfg = Config.load(config_path)
                    svc.import_from_config(cfg)
                except Exception as e:
                    logger.warning(f"Could not import config.yaml: {e}")
    except Exception as e:
        logger.warning(f"Settings seed skipped: {e}")
    finally:
        session.close()

    # Expose to the rest of the app via request.app.state
    app.state.db_manager = db_manager
    app.state.first_run = first_run
    logger.info("Application startup complete.")

    yield

    # Shutdown
    db_manager.dispose()
    logger.info("Application shutdown complete.")


# ── App factory ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="VajraStocks — NSE Quantitative Analysis Platform",
    description="Local-first stock analysis, screening, portfolio tracking, and AI-powered research.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — open for local dev; tighten in production via settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gzip for large JSON payloads (chart data)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.get("/health")
def health_check():
    """API liveness probe."""
    return {"status": "HEALTHY", "version": "1.0.0"}


# ── Routes ─────────────────────────────────────────────────────────────────────
from stocks.api.v1.router import api_router  # noqa: E402

app.include_router(api_router)

# ── Serve Vite frontend build ──────────────────────────────────────────────────
# Resolves the frontend/dist directory using multiple strategies so it works
# regardless of how uvicorn is launched (cwd, installed package, etc.)
def _find_frontend_dist() -> Path | None:
    here = Path(__file__).resolve()
    # Repo layout: <root>/python/src/stocks/api/main.py  →  <root>/frontend/dist
    candidates = [
        here.parent.parent.parent.parent.parent / "frontend" / "dist",  # <root>/frontend/dist
        here.parent.parent.parent.parent / "frontend" / "dist",          # legacy (pre-restructure)
        Path.cwd() / "frontend" / "dist",
        Path.cwd().parent / "frontend" / "dist",                          # when cwd == <root>/python
    ]
    for p in candidates:
        if (p / "index.html").exists():
            return p
    return None

_frontend_dist = _find_frontend_dist()
if _frontend_dist:
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    # Mount /assets and other static asset directories explicitly
    _assets_dir = _frontend_dist / "assets"
    if _assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")

    # Catch-all: serve index.html for any unknown path (SPA routing)
    # This must be registered LAST so API routes take priority
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        # Try to serve a real file first (favicon, icons, etc.)
        candidate = _frontend_dist / full_path
        if candidate.is_file():
            return FileResponse(str(candidate))
        # Fall back to index.html for all SPA routes
        return FileResponse(str(_frontend_dist / "index.html"))

    logger.info(f"Serving frontend from: {_frontend_dist}")
else:
    logger.warning("frontend/dist not found — run 'npm run build' in the frontend directory")
