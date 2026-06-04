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


def _data_dir() -> Path:
    """
    User-writable directory for the SQLite database, logs, etc.

    • Windows:  %APPDATA%\\VajraStocks\\data
    • macOS:    ~/Library/Application Support/VajraStocks/data
    • Linux:    ~/.local/share/VajraStocks/data

    Never the install dir (Program Files is read-only for normal users).
    """
    app_name = "VajraStocks"
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    d = base / app_name / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


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

    # ── Point SQLite to the user-writable data dir (absolute path avoids cwd issues)
    sqlite_url = f"sqlite:///{data / 'vajra.db'}"
    os.environ.setdefault("VAJRA_DB_URL", sqlite_url)
    os.environ.setdefault("VAJRA_DATA_DIR", str(data))

    # ── Alembic and config paths — used by main.py via env (see below)
    alembic_ini = bundle / "alembic.ini"
    if alembic_ini.exists():
        os.environ.setdefault("VAJRA_ALEMBIC_INI", str(alembic_ini))
    config_yaml = bundle / "config" / "config.yaml"
    if config_yaml.exists():
        os.environ.setdefault("VAJRA_CONFIG_YAML", str(config_yaml))

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
