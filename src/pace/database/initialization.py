"""Safe, idempotent initialization for Pace's local SQLite database."""

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig

from pace.config.settings import PROJECT_ROOT, settings
from pace.database.engine import (
    assert_sqlite_foreign_key_integrity,
    secure_sqlite_database_file,
)


def initialize_database(*, database_url: str | None = None) -> None:
    """Apply reviewed migrations without touching athlete data or Garmin tokens."""

    alembic_config = AlembicConfig(PROJECT_ROOT / "alembic.ini")
    url = database_url or settings.database_url
    alembic_config.set_main_option("sqlalchemy.url", url)
    assert_sqlite_foreign_key_integrity(url)
    alembic_command.upgrade(alembic_config, "head")
    secure_sqlite_database_file(url)
