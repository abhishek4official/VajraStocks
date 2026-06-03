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

# Load application config dynamically
app_config = Config.load()
db_url = app_config.database.connection_string

# Bootstrap database and localdb instance before any connection attempt
from stocks.db.connection import ensure_localdb_started, create_database_if_not_exists
ensure_localdb_started()
create_database_if_not_exists(db_url)

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
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
