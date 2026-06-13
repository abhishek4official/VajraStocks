"""
Database connection with automatic LocalDB named-pipe fallback.

The standard (localdb)\\MSSQLLocalDB connection string only works when the
calling process runs in the same interactive Windows session as the LocalDB
instance. When running from a subprocess or non-interactive context the ODBC
driver cannot resolve the instance name, so we fall back to auto-discovering
the active named pipe from the Windows pipe namespace.
"""

import subprocess
from typing import TYPE_CHECKING

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

if TYPE_CHECKING:
    import pyodbc

try:
    import pyodbc as _pyodbc  # type: ignore[import]
    _PYODBC_AVAILABLE = True
except ImportError:
    _pyodbc = None  # type: ignore[assignment]
    _PYODBC_AVAILABLE = False


def _discover_localdb_pipe() -> str | None:
    """Return the active LocalDB named pipe (e.g. np:\\\\.\\pipe\\LOCALDB#XXXX\\tsql\\query)."""
    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                r"Get-ChildItem '\\.\pipe\' | "
                r"Where-Object {$_.Name -like 'LOCALDB*'} | "
                r"Select-Object -First 1 -ExpandProperty Name",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        name = result.stdout.strip()
        if result.returncode == 0 and name:
            return rf"np:\\.\pipe\{name}"
    except Exception:
        pass
    return None


def get_engine(conn_str: str | None = None) -> Engine:
    """
    Return a SQLAlchemy engine connected to vajra_stocks.

    Tries the standard LocalDB URL first.  If that fails (non-interactive
    process context), discovers the active named pipe and connects via that.
    """
    from VajraML.config import DB_CONN_STR

    primary = conn_str or DB_CONN_STR

    try:
        engine = create_engine(primary, pool_pre_ping=False, echo=False)
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        return engine
    except Exception:
        pass

    pipe = _discover_localdb_pipe()
    if not pipe:
        raise ConnectionError(
            "Cannot connect to vajra_stocks LocalDB.\n"
            "Ensure the VajraStocks app has been opened at least once to start the instance."
        )

    if not _PYODBC_AVAILABLE:
        raise ImportError(
            "pyodbc is required for the named-pipe LocalDB fallback but is not installed. "
            "Install it with: pip install pyodbc"
        )

    def _creator():
        return _pyodbc.connect(
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={pipe};"
            "DATABASE=vajra_stocks;"
            "Trusted_Connection=yes;"
            "Encrypt=no;",
            timeout=15,
        )

    return create_engine("mssql+pyodbc://", creator=_creator, echo=False)
