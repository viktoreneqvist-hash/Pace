from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy.engine import make_url

from alembic import context

from pace.config.settings import settings
from pace.database.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_database_url() -> str:
    """Use an explicit Alembic URL or Pace's configured local database."""

    configured_url = config.get_main_option("sqlalchemy.url")

    if configured_url.startswith("driver://"):
        return settings.database_url

    return configured_url


def secure_sqlite_database_file(database_url: str) -> None:
    """Apply owner-only permissions after a direct Alembic SQLite migration.

    This deliberately lives in Alembic's environment instead of importing the
    application engine module, whose module-level engine would connect to the
    default Pace database during a migration against an explicitly configured
    database.
    """

    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" or url.database in (None, "", ":memory:"):
        return

    database_path = Path(url.database).expanduser()
    if database_path.exists() and database_path.stat().st_mode & 0o777 != 0o600:
        database_path.chmod(0o600)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_database_url()
    context.configure(
        url=url,
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
    database_url = get_database_url()
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = database_url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    secure_sqlite_database_file(database_url)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
