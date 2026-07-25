from sqlalchemy import inspect, text

from pace.database import engine


def test_initial_migration_creates_all_pace_tables():
    inspector = inspect(engine)

    assert {
        "activities",
        "context_events",
        "daily_metrics",
        "sync_runs",
    }.issubset(inspector.get_table_names())


def test_database_connection_uses_sqlite():
    with engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1
