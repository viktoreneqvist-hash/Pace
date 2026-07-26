from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from pace.database.engine import build_engine, engine


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_initial_migration_creates_all_pace_tables():
    inspector = inspect(engine)

    assert {
        "activities",
        "context_events",
        "daily_metrics",
        "races",
        "sync_runs",
    }.issubset(inspector.get_table_names())


def test_database_connection_uses_sqlite():
    with engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1


def test_new_sqlite_directory_and_database_are_owner_only(tmp_path: Path):
    database_directory = tmp_path / "private-data"
    database_path = database_directory / "pace.db"
    private_engine = build_engine(f"sqlite:///{database_path}")

    with private_engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    assert database_directory.stat().st_mode & 0o777 == 0o700
    assert database_path.stat().st_mode & 0o777 == 0o600
    private_engine.dispose()


def test_existing_custom_database_directory_keeps_its_mode(tmp_path: Path):
    database_directory = tmp_path / "shared"
    database_directory.mkdir(mode=0o755)
    database_directory.chmod(0o755)
    database_path = database_directory / "pace.db"
    custom_engine = build_engine(f"sqlite:///{database_path}")

    with custom_engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    assert database_directory.stat().st_mode & 0o777 == 0o755
    assert database_path.stat().st_mode & 0o777 == 0o600
    custom_engine.dispose()


def test_direct_alembic_upgrade_secures_a_new_sqlite_database(tmp_path: Path):
    database_path = tmp_path / "alembic-created.db"
    alembic_config = Config(PROJECT_ROOT / "alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")

    command.upgrade(alembic_config, "head")

    assert database_path.stat().st_mode & 0o777 == 0o600
