"""Database access for Pace."""

from sqlalchemy import text

from pace.database.engine import build_engine, engine
from pace.database.models import Base
from pace.database.session import SessionFactory, session_scope


def check_database_connection() -> str:
    """Verify the database connection and return its dialect name."""

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return engine.dialect.name


__all__ = [
    "Base",
    "SessionFactory",
    "build_engine",
    "check_database_connection",
    "engine",
    "session_scope",
]
