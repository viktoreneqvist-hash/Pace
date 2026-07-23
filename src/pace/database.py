from pathlib import Path
import os

from sqlalchemy import create_engine, text

from pace.models.activity import Base

DEFAULT_DATABASE_URL = "sqlite:///data/pace.db"
DATABASE_URL = os.getenv("PACE_DATABASE_URL", DEFAULT_DATABASE_URL)

engine = create_engine(DATABASE_URL)

def check_database_connection() -> str:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        return engine.dialect.name

def create_database_tables() -> None:
    if DATABASE_URL.startswith("sqlite:///"):
        Path(DATABASE_URL.removeprefix("sqlite:///")).parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    Base.metadata.create_all(engine)
