"""Database access for Pace."""

from sqlalchemy import text

from pace.database.engine import build_engine, engine
from pace.database.models.base import Base
from pace.database.session import SessionFactory, session_scope


def check_database_connection() -> str:
    """Verify the database connection and return its dialect name."""

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return engine.dialect.name


def create_database_tables() -> None:
    """Create the currently registered database tables.

    This function temporarily preserves compatibility with the existing tests.
    Alembic migrations will replace direct table creation in a later step.
    """

    import pace.models.activity  # noqa: F401

    Base.metadata.create_all(engine)


__all__ = [
    "Base",
    "SessionFactory",
    "build_engine",
    "check_database_connection",
    "create_database_tables",
    "engine",
    "session_scope",
]
