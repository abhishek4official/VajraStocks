import sys
from pathlib import Path

# Add project src directory to sys.path to allow absolute imports of stocks package
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from logging.config import fileConfig
from sqlalchemy import create_engine, pool
from alembic import context

# Import our custom Config and Base metadata
from stocks.config import Config
from stocks.db.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# target_metadata is set to our declarative model base
target_metadata = Base.metadata

# Load application config — prefer per-user VajraStocks dir, fall back to local config/config.yaml
import os as _os
import sys as _sys

def _alembic_user_config_path() -> "Path | None":
    """Returns the platform-appropriate user config.yaml path for Alembic to use."""
    # Explicit override (frozen launcher / Docker)
    env = _os.environ.get("VAJRA_CONFIG_YAML")
    if env:
        return Path(env)
    if _sys.platform == "win32":
        _appdata = _os.environ.get("APPDATA", "")
        return Path(_appdata) / "VajraStocks" / "config.yaml" if _appdata else None
    if _sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "VajraStocks" / "config.yaml"
    _xdg = _os.environ.get("XDG_DATA_HOME", "")
    _base = Path(_xdg) if _xdg else Path.home() / ".local" / "share"
    return _base / "VajraStocks" / "config.yaml"

_user_cfg = _alembic_user_config_path()
if _user_cfg and _user_cfg.exists():
    app_config = Config.load(_user_cfg)
else:
    app_config = Config.load()

db_url = app_config.database.connection_string

# Bootstrap database and localdb instance before any connection attempt
if db_url.lower().startswith("mssql"):
    from stocks.db.connection import ensure_localdb_started, create_mssql_database_if_not_exists
    ensure_localdb_started()
    create_mssql_database_if_not_exists(db_url)

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = create_engine(
        db_url,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
