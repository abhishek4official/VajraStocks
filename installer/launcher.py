"""
PyInstaller entry point — starts the VajraStocks FastAPI server via uvicorn,
then opens the default browser.  This file is the script given to PyInstaller,
not stocks/api/main.py (which only defines the ASGI app object and would exit
immediately if run as a script).
"""
import multiprocessing
import os
import sys
import webbrowser
from pathlib import Path


def _resource_root() -> Path:
    """Return the directory that contains config/, migrations/, frontend/dist/."""
    if getattr(sys, "frozen", False):
        # Running inside a PyInstaller bundle — sys._MEIPASS is the temp/onedir root
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]  # noqa: SLF001
    # Running from source (dev)
    return Path(__file__).resolve().parent.parent


def main() -> None:
    # Make bundled resources visible to the application
    resource_root = _resource_root()
    os.environ.setdefault("VAJRA_RESOURCE_ROOT", str(resource_root))

    # Ensure the data directory exists next to the executable (user-writable)
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
    else:
        exe_dir = Path(__file__).parent
    data_dir = exe_dir / "data"
    data_dir.mkdir(exist_ok=True)
    os.environ.setdefault("VAJRA_DATA_DIR", str(data_dir))

    host = "127.0.0.1"
    port = 8000

    # Open browser slightly after server starts (uvicorn logs show it's ready)
    import threading
    import time

    def _open_browser() -> None:
        time.sleep(2)
        webbrowser.open(f"http://{host}:{port}")

    threading.Thread(target=_open_browser, daemon=True).start()

    import uvicorn
    uvicorn.run(
        "stocks.api.main:app",
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    # Required on Windows for PyInstaller + multiprocessing
    multiprocessing.freeze_support()
    main()
