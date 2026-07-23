from sqlalchemy import inspect

from pace.database import create_database_tables, engine


def test_create_database_tables():
    create_database_tables()

    inspector = inspect(engine)

    assert "activities" in inspector.get_table_names()
