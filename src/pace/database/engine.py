"""SQLAlchemy engine configuration."""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from pace.config.settings import settings


def ensure_sqlite_directory(database_url: str) -> None:
    """Create the parent directory for a file-based SQLite database."""

    if not database_url.startswith("sqlite:///"):
        return

    if ":memory:" in database_url:
        return

    database_path = Path(database_url.removeprefix("sqlite:///"))
    database_path.parent.mkdir(parents=True, exist_ok=True)


def build_engine(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine for Pace."""

    url = database_url or settings.database_url

    ensure_sqlite_directory(url)

    engine_options: dict = {
        "pool_pre_ping": True,
    }

    if url.startswith("sqlite"):
        engine_options["connect_args"] = {
            "check_same_thread": False,
        }

    return create_engine(url, **engine_options)


engine = build_engine()
