"""SQLAlchemy engine configuration."""

from pathlib import Path
import sqlite3

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url

from pace.config.settings import PROJECT_ROOT, settings


def sqlite_database_path(database_url: str) -> Path | None:
    """Return the filesystem path for a file-based SQLite database."""

    url = make_url(database_url)

    if url.get_backend_name() != "sqlite" or url.database in (None, "", ":memory:"):
        return None

    return Path(url.database).expanduser()


def ensure_sqlite_directory(database_url: str) -> Path | None:
    """Create a private parent directory for a file-based SQLite database.

    Pace hardens its own default ``data`` directory. For a configured database
    inside an existing shared directory, Pace leaves the directory mode alone
    and secures only the database file.
    """

    database_path = sqlite_database_path(database_url)
    if database_path is None:
        return None

    database_directory = database_path.parent
    directory_existed = database_directory.exists()
    database_directory.mkdir(mode=0o700, parents=True, exist_ok=True)

    default_data_directory = PROJECT_ROOT / "data"
    should_be_private = (
        not directory_existed or database_directory == default_data_directory
    )
    if should_be_private and database_directory.stat().st_mode & 0o777 != 0o700:
        database_directory.chmod(0o700)

    return database_path


def secure_sqlite_database_file(database_url: str) -> None:
    """Apply owner-only permissions to an existing SQLite database file."""

    database_path = sqlite_database_path(database_url)
    if (
        database_path is not None
        and database_path.exists()
        and database_path.stat().st_mode & 0o777 != 0o600
    ):
        database_path.chmod(0o600)


def assert_sqlite_foreign_key_integrity(database_url: str) -> None:
    """Refuse an upgrade that would hide existing SQLite referential damage."""

    database_path = sqlite_database_path(database_url)
    if database_path is None or not database_path.exists():
        return
    with sqlite3.connect(database_path) as connection:
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError(
            "SQLite foreign-key integrity check failed; repair the local database before upgrade."
        )


def build_engine(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine for Pace."""

    url = database_url or settings.database_url

    sqlite_path = ensure_sqlite_directory(url)

    engine_options: dict = {
        "pool_pre_ping": True,
    }

    if url.startswith("sqlite"):
        engine_options["connect_args"] = {
            "check_same_thread": False,
        }

    pace_engine = create_engine(url, **engine_options)

    if url.startswith("sqlite"):

        @event.listens_for(pace_engine, "connect")
        def configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
            """Enable SQLite referential integrity on every Pace connection."""

            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    if sqlite_path is not None:

        @event.listens_for(pace_engine, "connect")
        def secure_sqlite_file(_dbapi_connection, _connection_record) -> None:
            """Keep the local database owner-readable and owner-writable only."""

            secure_sqlite_database_file(url)

    return pace_engine


engine = build_engine()
