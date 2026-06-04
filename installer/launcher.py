"""
PyInstaller entry point — starts the VajraStocks FastAPI server via uvicorn,
then opens the default browser.

Responsibilities:
  • Locate the bundle's resource root (config/, migrations/, frontend/dist/)
  • Point SQLite to a user-writable data directory (not the install dir)
  • Find a free port if 8000 is already in use
  • Open the browser only after the HTTP server is actually accepting connections
"""

import multiprocessing
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


# ── Resource and data paths ───────────────────────────────────────────────────

def _bundle_root() -> Path:
    """
    In a frozen (PyInstaller onedir) build sys._MEIPASS == the bundle directory.
    In dev mode it's two levels above this file: installer/ → repo root.
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]  # noqa: SLF001
    return Path(__file__).resolve().parent.parent


def _app_dir() -> Path:
    """
    User-writable root for all VajraStocks user data.

    • Windows:  %APPDATA%\\VajraStocks
    • macOS:    ~/Library/Application Support/VajraStocks
    • Linux:    ~/.local/share/VajraStocks

    Never the install dir (Program Files is read-only for normal users).
    """
    app_name = "VajraStocks"
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    d = base / app_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _data_dir() -> Path:
    d = _app_dir() / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _user_config(bundle: Path) -> Path:
    """
    Return a user-writable config.yaml path (%APPDATA%/VajraStocks/config.yaml).
    On first run, copies the bundled default config there as a starting point.
    Subsequent writes (e.g. Settings UI saves) update this file, never the
    read-only bundle inside Program Files.
    """
    import shutil
    user_cfg = _app_dir() / "config.yaml"
    if not user_cfg.exists():
        bundled = bundle / "config" / "config.yaml"
        if bundled.exists():
            shutil.copy2(bundled, user_cfg)
    return user_cfg


# ── Free-port finder ──────────────────────────────────────────────────────────

def _find_free_port(preferred: int = 8000) -> int:
    """Return `preferred` if it is free, otherwise the next available port."""
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    # Last resort: let the OS pick any free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ── Browser opener ────────────────────────────────────────────────────────────

def _open_browser_when_ready(host: str, port: int, timeout: float = 60.0) -> None:
    """Poll the server until it accepts connections, then open the browser."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                webbrowser.open(f"http://{host}:{port}")
                return
        except OSError:
            time.sleep(0.3)
    # Server never came up — nothing to open


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    bundle = _bundle_root()
    data   = _data_dir()

    # ── Expose resource root so main.py can find config/, migrations/, frontend/
    os.environ.setdefault("VAJRA_RESOURCE_ROOT", str(bundle))

    os.environ.setdefault("VAJRA_DATA_DIR", str(data))

    # ── Resolve the database connection string ────────────────────────────────
    # Priority:
    #   1. VAJRA_DB_URL already set in environment (Docker / CI / test override)
    #   2. connection_string in user config.yaml  (user changed DB via Settings)
    #   3. SQLite in the user data dir             (safe default for new installs)
    sqlite_url = f"sqlite:///{data / 'vajra.db'}"
    if "VAJRA_DB_URL" not in os.environ:
        db_url = sqlite_url          # default
        try:
            import yaml as _yaml
            _cfg_path = _app_dir() / "config.yaml"
            if _cfg_path.exists():
                with open(_cfg_path, encoding="utf-8") as _f:
                    _cfg = _yaml.safe_load(_f) or {}
                _cs = _cfg.get("database", {}).get("connection_string", "")
                if _cs and _cs.strip():
                    db_url = _cs.strip()
        except Exception:
            pass                     # any parse error → keep SQLite default
        os.environ["VAJRA_DB_URL"] = db_url

    # ── Alembic ini — read-only, lives in the bundle (no writes needed)
    alembic_ini = bundle / "alembic.ini"
    if alembic_ini.exists():
        os.environ.setdefault("VAJRA_ALEMBIC_INI", str(alembic_ini))

    # ── config.yaml — must be user-writable (Settings UI saves changes here)
    # Copy bundled default to %APPDATA%/VajraStocks/ on first run, then always
    # point to the AppData copy so writes never hit the read-only install dir.
    user_config = _user_config(bundle)
    os.environ.setdefault("VAJRA_CONFIG_YAML", str(user_config))

    # ── Change cwd to bundle so any remaining relative paths resolve correctly
    os.chdir(bundle)

    host = "127.0.0.1"
    port = _find_free_port(8000)

    threading.Thread(
        target=_open_browser_when_ready,
        args=(host, port),
        daemon=True,
    ).start()

    import uvicorn
    uvicorn.run(
        "stocks.api.main:app",
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    multiprocessing.freeze_support()   # must be first on Windows
    main()
